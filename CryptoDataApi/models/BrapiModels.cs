using System.Text.Json.Serialization;

namespace CryptoDataApi.Models
{
    // Map class
    public class BrapiResponse
    {
        [JsonPropertyName("results")]
        public List<BrapiResult>? Results { get; set; }
    }

    // Data class for each stock
    public class BrapiResult
    {
        [JsonPropertyName("symbol")]
        public string Symbol { get; set; } = string.Empty;

        [JsonPropertyName("regularMarketPrice")]
        public decimal RegularMarketPrice { get; set; }
        
        [JsonPropertyName("historicalDataPrice")]
        public List<BrapiHistoricalPrice>? HistoricalDataPrice { get; set; }
    }

    // Class for historical price data
    public class BrapiHistoricalPrice
    {
        [JsonPropertyName("date")]
        public long Date { get; set; } 

        [JsonPropertyName("close")]
        public decimal Close { get; set; }
    }
}