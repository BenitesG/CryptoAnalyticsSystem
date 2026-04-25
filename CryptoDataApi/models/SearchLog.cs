using System;

// Models for database and API responses
namespace CryptoDataApi.Models
{
    public class SearchLog
    {
        public int Id { get; set; }

        public string CoinName { get; set; } = string.Empty;
        
        public decimal PriceUsd { get; set; }

        public DateTime SearchDate { get; set; }
    }
}