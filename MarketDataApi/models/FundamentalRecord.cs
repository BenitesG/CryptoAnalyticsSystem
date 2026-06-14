using System.ComponentModel.DataAnnotations;

namespace MarketDataApi.Models;

public class FundamentalRecord
{
    [Key]
    public string Ticker { get; set; } = string.Empty;
    public string AssetType { get; set; } = string.Empty; 
    
    // Common Fields
    public string? SectorOrSegment { get; set; }
    public decimal? PriceToEarnings { get; set; } 
    public decimal? PriceToBook { get; set; } 
    public decimal? DividendYield { get; set; }

    // Stock Specific Fields
    public decimal? Roe { get; set; }
    public decimal? NetMargin { get; set; }
    public decimal? DebtToEbitda { get; set; }
    public decimal? MarketCap { get; set; }
    public decimal? EvEbit { get; set; }
    public decimal? EvEbitda { get; set; }
    public decimal? RevenueCagr5y { get; set; }
    public decimal? ProfitCagr5y { get; set; }

    // FII Specific Fields
    public string? FiiType { get; set; } 
    public decimal? Vacancy { get; set; }
    public int? PropertiesCount { get; set; }
    public decimal? ShareholdersCount { get; set; }
    
    // NEW FII FIELDS (From Fundamentus)
    public decimal? DailyLiquidity { get; set; } // VOL $ MÉD (2M)
    public decimal? NetWorth { get; set; }       // PATRIMÔNIO LÍQ
    public decimal? LastDividend { get; set; }   // ÚLTIMO RENDIMENTO

    // Cache Telemetry
    public DateTime LastUpdatedAt { get; set; }
}