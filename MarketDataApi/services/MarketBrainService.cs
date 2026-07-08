using System.Text.Json.Nodes;
using Microsoft.Extensions.Caching.Memory;
using System.Net;
using System.Net.Http.Json;
using MarketDataApi.Models;
using Microsoft.Extensions.Caching.Distributed;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;


namespace MarketDataApi.Services
{
        public class MarketBrainService 
        {
        private readonly HttpClient _httpClient;
        private readonly IMemoryCache _memoryCache;
        private readonly IDistributedCache _distributedCache; 
        private readonly ILogger<MarketBrainService> _logger;

        
        public MarketBrainService(
            HttpClient httpClient, 
            IMemoryCache memoryCache, 
            IDistributedCache distributedCache, 
            ILogger<MarketBrainService> logger)
        {
            _httpClient = httpClient;
            _memoryCache = memoryCache;
            _distributedCache = distributedCache; 
            _logger = logger;
        }

        public async Task<JsonObject?> GetFundamentalsAsync(string assetType, string ticker)
        {
            string normalizedTicker = ticker.Trim().ToUpperInvariant();
            string normalizedType = assetType.Trim().ToLowerInvariant();
            
            string cacheKey = $"fund_{normalizedType}_{normalizedTicker}";

            return await _memoryCache.GetOrCreateAsync(cacheKey, async (cacheOptions) =>
            {
                cacheOptions.AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(10);

                _logger.LogInformation("Cache miss for {CacheKey}. Fetching fundamentals from Python Engine.", cacheKey);

                using var response = await _httpClient.GetAsync($"/fundamentals/{normalizedType}/{normalizedTicker}");

                if (response.StatusCode == HttpStatusCode.NotFound)
                {
                    _logger.LogWarning("Fundamentals not found for {Ticker} in Python Engine.", normalizedTicker);
                    return null;
                }

                response.EnsureSuccessStatusCode();

                return await response.Content.ReadFromJsonAsync<JsonObject>();
            });
        }

        private string GeneratePortfolioHash(List<AssetAnalysisInput> assets)
        {
            var sortedAssets = assets.OrderBy(a => a.Ticker).ToList();
            
            var stateString = string.Join("|", sortedAssets.Select(a => 
                $"{a.Ticker}:{a.Quantity}:{a.AveragePrice}:{a.LivePrice}"
            ));

            using var sha256 = SHA256.Create();
            var bytes = Encoding.UTF8.GetBytes(stateString);
            var hashBytes = sha256.ComputeHash(bytes);
            
            return Convert.ToHexString(hashBytes).ToLowerInvariant();
        }

        public async Task<PortfolioAnalysisResponse?> AnalyzePortfolioWithCacheAsync(List<AssetAnalysisInput> assets)
        {
            var hash = GeneratePortfolioHash(assets);
            string cacheKey = $"portfolio_analysis_{hash}";

            var cachedData = await _distributedCache.GetAsync(cacheKey);
            
            if (cachedData != null)
            {
                _logger.LogInformation("Cache HIT in Redis for portfolio analysis with Hash: {Hash}", hash);
                
                return JsonSerializer.Deserialize<PortfolioAnalysisResponse>(cachedData);
            }

            _logger.LogInformation("Cache MISS in Redis for portfolio analysis with Hash: {Hash}. Calling Python...", hash);

            var response = await AnalyzePortfolioAsync(assets);

            if (response != null)
            {

                var serializedData = JsonSerializer.SerializeToUtf8Bytes(response);
                var cacheOptions = new DistributedCacheEntryOptions
                {
                    AbsoluteExpirationRelativeToNow = TimeSpan.FromHours(12)
                };
                
                await _distributedCache.SetAsync(cacheKey, serializedData, cacheOptions);
            }

            return response;
        }

        public async Task<PortfolioAnalysisResponse?> AnalyzePortfolioAsync(List<AssetAnalysisInput> assets)
        {
            var payload = new PortfolioAnalysisRequest(assets);

            var response = await _httpClient.PostAsJsonAsync("/analyze-portfolio", payload);

            if (!response.IsSuccessStatusCode)
            {
                throw new HttpRequestException($"MarketBrain service returned status {response.StatusCode}");
            }

            return await response.Content.ReadFromJsonAsync<PortfolioAnalysisResponse>();
        }
    }
}