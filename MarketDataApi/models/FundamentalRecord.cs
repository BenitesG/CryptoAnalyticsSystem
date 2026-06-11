using System.ComponentModel.DataAnnotations;

namespace MarketDataApi.Models;

public class FundamentalRecord
{
    [Key]
    public string Ticker { get; set; } = string.Empty;

    public string AssetType { get; set; } = string.Empty; 
    

    public string? SectorOrSegment { get; set; }
    public decimal? PriceToEarnings { get; set; } 
    public decimal? PriceToBook { get; set; } 
    public decimal? DividendYield { get; set; }

    public decimal? Roe { get; set; }
    public decimal? NetMargin { get; set; }
    public decimal? DebtToEbitda { get; set; }
    public decimal? Cagr5y { get; set; }

    public string? FiiType { get; set; } 
    public decimal? Vacancy { get; set; }
    public int? PropertiesCount { get; set; }
    public decimal? ShareholdersCount { get; set; }

    public DateTime LastUpdatedAt { get; set; }
}