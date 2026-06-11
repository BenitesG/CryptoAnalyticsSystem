using MarketDataApi.Models; 
using System.Text.Json;
using Microsoft.Extensions.Caching.Memory;
using System.Net; 

namespace MarketDataApi.Services 
{
    public class BrapiService : IMarketDataService
    {
        private readonly HttpClient _httpClient;
        private readonly IMemoryCache _cache;
        private readonly ILogger<BrapiService> _logger;
        private readonly IConfiguration _config;
        private readonly string _brapiBaseUrl;

        public BrapiService(HttpClient httpClient, IMemoryCache cache, ILogger<BrapiService> logger, IConfiguration config)
        {
            _httpClient = httpClient;
            _cache = cache;
            _logger = logger;
            _config = config;
            _brapiBaseUrl = config["Brapi:BaseUrl"]
                ?? throw new InvalidOperationException("Configuration 'Brapi:BaseUrl' is required.");
            _httpClient.DefaultRequestHeaders.Add("User-Agent", "MarketDataApi");
        }

        public async Task<decimal?> GetPriceAsync(string ticker)
        {
            string normalizedTicker = ticker.Trim().ToUpperInvariant();
            _logger.LogInformation("Searching for price of {ticker} on B3...", normalizedTicker);
            string cacheKey = $"price_b3_{normalizedTicker}";

            return await _cache.GetOrCreateAsync<decimal?>(cacheKey, async (cacheOptions) =>
            {
                cacheOptions.AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(1);
                var token = _config["Brapi:BrapiApiKey"];

                string url = $"{_brapiBaseUrl}/quote/{normalizedTicker}?token={token}";
                
                using var response = await _httpClient.GetAsync(url);
                
                if (response.StatusCode == HttpStatusCode.NotFound) 
                {
                    _logger.LogWarning("Ticker {ticker} not found on Brapi.", normalizedTicker);
                    return null; 
                }

                response.EnsureSuccessStatusCode();

                var text = await response.Content.ReadAsStringAsync();
                var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
                var data = JsonSerializer.Deserialize<BrapiResponse>(text, options);

                return data?.Results?.FirstOrDefault()?.RegularMarketPrice;
            });
        }

        public async Task<object?> GetHistoryAsync(string ticker)
        {
            string normalizedTicker = ticker.Trim().ToUpperInvariant();
            _logger.LogInformation("Fetching history for {ticker} on B3...", normalizedTicker);
            string cacheKey = $"hist_b3_{normalizedTicker}";

            return await _cache.GetOrCreateAsync(cacheKey, async (cacheOptions) =>
            {
                cacheOptions.AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(5);
                var token = _config["Brapi:BrapiApiKey"];
                string url = $"{_brapiBaseUrl}/quote/{normalizedTicker}?range=5d&interval=1d&token={token}";
                
                using var response = await _httpClient.GetAsync(url);
                
                if (response.StatusCode == HttpStatusCode.NotFound) return null;
                
                response.EnsureSuccessStatusCode();

                var text = await response.Content.ReadAsStringAsync();
                var jsonOptions = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
                var data = JsonSerializer.Deserialize<BrapiResponse>(text, jsonOptions);

                if (data?.Results == null || data.Results.Count == 0) return null;

                var history = data.Results[0].HistoricalDataPrice;
                List<decimal> onlyPrice;

                if (history == null || history.Count < 2)
                {
                    _logger.LogWarning("Historical data empty or insufficient from Brapi for {Ticker}. Applying flat-line fallback.", normalizedTicker);
                    
                    var currentPrice = data.Results[0].RegularMarketPrice;
                    
                    onlyPrice = Enumerable.Repeat(currentPrice, 5).ToList();
                }
                else
                {
                    onlyPrice = history.Select(h => h.Close).ToList();
                }

                var requestPython = new PythonAnalyzeRequest
                {
                    CoinName = normalizedTicker,
                    Prices = onlyPrice
                };

                try 
                {
                    var jsonContent = new StringContent(JsonSerializer.Serialize(requestPython), System.Text.Encoding.UTF8, "application/json");
                    var brainUrl = _config["MarketBrain:BaseUrl"] ?? "http://localhost:8000";
                    using var pythonResponse = await _httpClient.PostAsync($"{brainUrl}/analyze", jsonContent);
                    pythonResponse.EnsureSuccessStatusCode();

                    var pythonText = await pythonResponse.Content.ReadAsStringAsync();
                    var analysisResult = JsonSerializer.Deserialize<PythonAnalyzeResponse>(pythonText, jsonOptions);

                    return new {
                        average = Math.Round(onlyPrice.Average(), 2),
                        max = Math.Round(onlyPrice.Max(), 2),
                        min = Math.Round(onlyPrice.Min(), 2),
                        volatility = analysisResult?.Volatility,
                        trend = analysisResult?.Trend ?? "STABLE",                 
                        percentage_change = analysisResult?.PercentageChange,
                        prices = onlyPrice,
                        action_signal = analysisResult?.ActionSignal ?? "HOLD",
                    };
                }

                catch (Exception ex)
                {
                    _logger.LogError(ex, "Analytical Engine (Python) failed for {Ticker}", normalizedTicker);
                    throw new HttpRequestException(
                        $"Analytical Engine (Python) unavailable for {normalizedTicker}.",
                        ex,
                        HttpStatusCode.ServiceUnavailable);
                }
            });
        }
    }
}