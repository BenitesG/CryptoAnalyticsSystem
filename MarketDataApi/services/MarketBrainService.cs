using System.Text.Json.Nodes;
using Microsoft.Extensions.Caching.Memory;
using System.Net;
using System.Net.Http.Json;
using MarketDataApi.Models;

namespace MarketDataApi.Services
{
    public class MarketBrainService
    {
        private readonly HttpClient _httpClient;
        private readonly IMemoryCache _cache;
        private readonly ILogger<MarketBrainService> _logger;

        public MarketBrainService(HttpClient httpClient, IMemoryCache cache, ILogger<MarketBrainService> logger)
        {
            _httpClient = httpClient;
            _cache = cache;
            _logger = logger;
        }

        public async Task<JsonObject?> GetFundamentalsAsync(string assetType, string ticker)
        {
            string normalizedTicker = ticker.Trim().ToUpperInvariant();
            string normalizedType = assetType.Trim().ToLowerInvariant();
            
            string cacheKey = $"fund_{normalizedType}_{normalizedTicker}";

            return await _cache.GetOrCreateAsync(cacheKey, async (cacheOptions) =>
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

        public async Task<PortfolioAnalysisResponse?> AnalyzePortfolioAsync(List<AssetAnalysisInput> assets)
        {
            var payload = new PortfolioAnalysisRequest(assets);

            // Dispara a requisição POST para o Python
            var response = await _httpClient.PostAsJsonAsync("/analyze-portfolio", payload);

            if (!response.IsSuccessStatusCode)
            {
                // Se a chamada falhar, lançamos a exceção que o seu teste espera
                throw new HttpRequestException($"MarketBrain service returned status {response.StatusCode}");
            }

            // Retorna o resultado parseado automaticamente do JSON
            return await response.Content.ReadFromJsonAsync<PortfolioAnalysisResponse>();
        }
    }
}