using CryptoDataApi.Models;
using System.Text.Json;
using Microsoft.Extensions.Caching.Memory;

// Interact with coinGecko API and Python service, with caching to optimize performance
namespace CryptoDataApi.Services
{
    public class CoinGeckoService
    {
        private readonly HttpClient _httpClient;
        private readonly IMemoryCache _cache;

        public CoinGeckoService(HttpClient httpClient, IMemoryCache cache)
        {
            _httpClient = httpClient;
            _cache = cache;
            _httpClient.DefaultRequestHeaders.Add("User-Agent", "CryptoDataApi");
        }   

        // Get historical price data and analysis for a specific coin, with caching for 5 minutes
        public async Task<object?> GetHistoryAsync(string coin)
        {
            string cacheKey = $"hist_{coin}";

            var dadosFinais = await _cache.GetOrCreateAsync(cacheKey, async (opcoesDoCache) =>
            {
                opcoesDoCache.AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(5);

                string url = $"https://api.coingecko.com/api/v3/coins/{coin}/market_chart?vs_currency=usd&days=7";
                var texto = await _httpClient.GetStringAsync(url);
                var opcoesJson = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };

                // Deserialize the response to get price data
                var dados = JsonSerializer.Deserialize<MarketChartResponse>(texto, opcoesJson);

                if (dados?.Prices == null || dados.Prices.Count == 0) return null;

                var apenasPrecos = dados.Prices.Select(p => p[1]).ToList();

                var requestProPython = new PythonAnalyzeRequest
                {
                    CoinName = coin,
                    Prices = apenasPrecos
                };

                var conteudoJson = new StringContent(JsonSerializer.Serialize(requestProPython), System.Text.Encoding.UTF8, "application/json");

                var respostaPython = await _httpClient.PostAsync("http://localhost:8000/analyze", conteudoJson);

                respostaPython.EnsureSuccessStatusCode(); 

                var textoPython = await respostaPython.Content.ReadAsStringAsync();
                var opcoes = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };

                var analiseDoCerebro = JsonSerializer.Deserialize<PythonAnalyzeResponse>(textoPython, opcoes);

                return new {
                    average = Math.Round(apenasPrecos.Average(), 2),
                    max = Math.Round(apenasPrecos.Max(), 2),
                    min = Math.Round(apenasPrecos.Min(), 2),
                    trend = analiseDoCerebro?.Trend,                 
                    percentage_change = analiseDoCerebro?.PercentageChange
                };

            });

            return dadosFinais;
            }

        // Get current price of a specific coin, with caching for 1 minute
        public async Task<decimal?> GetPriceAsync(string coin)
        {
            string cacheKey = $"price_{coin}";

            var dadosFinais = await _cache.GetOrCreateAsync(cacheKey, async (opcoesDoCache) =>
            {
                opcoesDoCache.AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(1);

                string url = $"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd";
                var texto = await _httpClient.GetStringAsync(url);
                var opcoes = new JsonSerializerOptions { PropertyNameCaseInsensitive= true};

                // Deserialize the response to get the current price
                var dados = JsonSerializer.Deserialize<Dictionary<string, Dictionary<string, decimal>>>(texto, opcoes);

                if (dados != null && dados.ContainsKey(coin))
                {
                    return dados[coin]["usd"];
                }
                return (decimal?)null;
            });

            return dadosFinais;
        }
    }
}