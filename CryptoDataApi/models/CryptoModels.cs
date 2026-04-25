using System;
using System.Text.Json.Serialization;

namespace CryptoDataApi.Models
{
    // CoinGecko API response models
    public class CoinGeckoResponse
    {
        [JsonExtensionData]
        public Dictionary<string, object>? ExtraData { get; set; }
    }
    public class MarketChartResponse
    {
        public List<decimal[]>? Prices { get; set; }
    }
    public class BitcoinData
    {
        public decimal Usd { get; set; }
    }

    // Python Response model
    public class PythonAnalyzeRequest
    {
        [JsonPropertyName("coin_name")]
        public string CoinName { get; set; } = string.Empty;
        [JsonPropertyName("prices")]
        public List<decimal> Prices { get; set; } = new List<decimal>();
    }

    public class PythonAnalyzeResponse
    {
        [JsonPropertyName("trend")]
        public string Trend { get; set; } = string.Empty;

        [JsonPropertyName("percentage_change")]
        public decimal PercentageChange { get; set; }
    }
}