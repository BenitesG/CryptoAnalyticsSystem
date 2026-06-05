using MarketDataApi.Models;
using System.Text.Json;
using Microsoft.Extensions.Caching.Memory;

// Interact with coinGecko API and Python service, with caching to optimize performance
namespace MarketDataApi.Services
{
    public class CoinGeckoService : IMarketDataService
    {
        private readonly HttpClient _httpClient;
        private readonly IMemoryCache _cache;
        private readonly ILogger<CoinGeckoService> _logger;
        private readonly IConfiguration _config;

        public CoinGeckoService(HttpClient httpClient, IMemoryCache cache, ILogger<CoinGeckoService> logger, IConfiguration config)
        {
            _httpClient = httpClient;
            _cache = cache;
            _logger = logger;
            _config = config; // Salva a config
            _httpClient.DefaultRequestHeaders.Add("User-Agent", "MarketDataApi");
        }

        public async Task<object?> GetHistoryAsync(string coin)
        {
            string cacheKey = $"hist_{coin}";

            var finalData = await _cache.GetOrCreateAsync(cacheKey, async (cacheOptions) =>
            {
                cacheOptions.AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(5);

                _logger.LogInformation("Cache miss for {CacheKey}. Fetching history from CoinGecko.", cacheKey);

                string url = $"https://api.coingecko.com/api/v3/coins/{coin}/market_chart?vs_currency=usd&days=7";

                string text;
                try
                {
                    text = await _httpClient.GetStringAsync(url);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to fetch history from CoinGecko for coin {Coin}.", coin);
                    throw;
                }

                var optionsJson = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };

                // Deserialize the response to get price data
                var data = JsonSerializer.Deserialize<MarketChartResponse>(text, optionsJson);

                if (data?.Prices == null || data.Prices.Count == 0)
                {
                    _logger.LogWarning("No price data returned from CoinGecko for coin {Coin}.", coin);
                    return null;
                }

                var onlyPrice = data.Prices.Select(p => p[1]).ToList();

                var pythonRequest = new PythonAnalyzeRequest
                {
                    CoinName = coin,
                    Prices = onlyPrice
                };

                var jsonContent = new StringContent(JsonSerializer.Serialize(pythonRequest), System.Text.Encoding.UTF8, "application/json");

                _logger.LogInformation("Calling Python analyze service for coin {Coin}.", coin);

                try
                {
                    var brainUrl = _config["MarketBrain:BaseUrl"] ?? "http://localhost:8000";
                    
                    // O 'using' aqui garante que a conexão será fechada e limpa da memória!
                    using var pythonResponse = await _httpClient.PostAsync($"{brainUrl}/analyze", jsonContent);
                    pythonResponse.EnsureSuccessStatusCode();

                    var pythonText = await pythonResponse.Content.ReadAsStringAsync();
                    var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };

                    var brainAnalysis = JsonSerializer.Deserialize<PythonAnalyzeResponse>(pythonText, options);

                    return new {
                        average = Math.Round(onlyPrice.Average(), 2),
                        max = Math.Round(onlyPrice.Max(), 2),
                        min = Math.Round(onlyPrice.Min(), 2),
                        volatility = brainAnalysis?.Volatility,
                        trend = brainAnalysis?.Trend,
                        percentage_change = brainAnalysis?.PercentageChange,
                        prices = brainAnalysis?.HistoricalPrices,
                        action_signal = brainAnalysis?.ActionSignal,
                    };
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to get analysis from Python service for coin {Coin}.", coin);
                    throw;
                }

            });

            return finalData;
        }

        // Get current price of a specific coin, with caching for 1 minute
        public async Task<decimal?> GetPriceAsync(string coin)
        {
            string cacheKey = $"price_{coin}";

            var finalData = await _cache.GetOrCreateAsync(cacheKey, async (cacheOptions) =>
            {
                cacheOptions.AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(1);

                _logger.LogInformation("Cache miss for {CacheKey}. Fetching price from CoinGecko.", cacheKey);

                string url = $"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd";

                string text;
                try
                {
                    text = await _httpClient.GetStringAsync(url);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to fetch price from CoinGecko for coin {Coin}.", coin);
                    throw;
                }

                var options = new JsonSerializerOptions { PropertyNameCaseInsensitive= true};

                // Deserialize the response to get the current price
                var data = JsonSerializer.Deserialize<Dictionary<string, Dictionary<string, decimal>>>(text, options);

                if (data != null && data.ContainsKey(coin))
                {
                    return data[coin]["usd"];
                }

                _logger.LogWarning("Price not found in CoinGecko response for coin {Coin}.", coin);
                return (decimal?)null;
            });

            return finalData;
        }
    }
}