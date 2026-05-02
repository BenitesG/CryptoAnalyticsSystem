using CryptoDataApi.Models;
using System.Text.Json;
using Microsoft.Extensions.Caching.Memory;

namespace CryptoDataApi.Services
{
    // Interact with Brapi API and Python service, with caching to optimize performance
    public class BrapiService : IMarketDataService
    {
        private readonly HttpClient _httpClient;
        private readonly IMemoryCache _cache;
        private readonly ILogger<BrapiService> _logger;
        private readonly IConfiguration _config;

        public BrapiService(HttpClient httpClient, IMemoryCache cache, ILogger<BrapiService> logger, IConfiguration config)
        {
            _httpClient = httpClient;
            _cache = cache;
            _logger = logger;
            _config = config;
            _httpClient.DefaultRequestHeaders.Add("User-Agent", "CryptoDataApi");
        }

        // Search for the current price of a stock on B3 using Brapi
        public async Task<decimal?> GetPriceAsync(string ticker)
        {
            _logger.LogInformation("Searching for price of {ticker} on B3 (Brapi)...", ticker);
            string cacheKey = $"price_b3_{ticker}";

            return await _cache.GetOrCreateAsync<decimal?>(cacheKey, async (cacheOptions) =>
            {
                cacheOptions.AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(1);

                var token = _config["Brapi:BrapiApiKey"];

                string url = $"https://brapi.dev/api/quote/{ticker}?token={token}";
                
                var text = await _httpClient.GetStringAsync(url);
                var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
                var data = JsonSerializer.Deserialize<BrapiResponse>(text, options);

                // Return a list of results, but we only care about the first one (if it exists)
                if (data?.Results != null && data.Results.Count > 0)
                {
                    return data.Results[0].RegularMarketPrice;
                }
                return (decimal?)null;
            });
        }

        // Search for the historical price of a stock on B3 using Brapi, and analyze it with the Python service
        public async Task<object?> GetHistoryAsync(string ticker)
        {
            string cacheKey = $"hist_b3_{ticker}";

            return await _cache.GetOrCreateAsync(cacheKey, async (cacheOptions) =>
            {
                cacheOptions.AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(5);

                var token = _config["Brapi:BrapiApiKey"];

                string url = $"https://brapi.dev/api/quote/{ticker}?range=5d&interval=1d&token={token}";
                
                var text = await _httpClient.GetStringAsync(url);
                var jsonOptions = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
                var data = JsonSerializer.Deserialize<BrapiResponse>(text
                , jsonOptions);

                if (data?.Results == null || data.Results.Count == 0) return null;

                var history = data.Results[0].HistoricalDataPrice;
                if (history == null || history.Count == 0) return null;

                var onlyPrice = history.Select(h => h.Close).ToList();

                // Re-use the same PythonAnalyzeRequest and PythonAnalyzeResponse classes we created para CoinGecko, since the structure it's the same
                var requestPython = new PythonAnalyzeRequest
                {
                    CoinName = ticker,
                    Prices = onlyPrice
                };

                var JsonContent = new StringContent(JsonSerializer.Serialize(requestPython), System.Text.Encoding.UTF8, "application/json");
                var pythonResponse = await _httpClient.PostAsync("http://localhost:8000/analyze", JsonContent);
                
                pythonResponse.EnsureSuccessStatusCode(); 

                var pythonText = await pythonResponse.Content.ReadAsStringAsync();
                var analysisResult = JsonSerializer.Deserialize<PythonAnalyzeResponse>(pythonText, jsonOptions);

                return new {
                    average = Math.Round(onlyPrice.Average(), 2),
                    max = Math.Round(onlyPrice.Max(), 2),
                    min = Math.Round(onlyPrice.Min(), 2),
                    volatility = analysisResult?.Volatility,
                    trend = analysisResult?.Trend,                 
                    percentage_change = analysisResult?.PercentageChange,
                    prices = analysisResult?.HistoricalPrices,
                };
            });
        }
    }
}