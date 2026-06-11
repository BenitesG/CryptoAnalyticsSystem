using MarketDataApi.Services;
using MarketDataApi.Data;
using Microsoft.EntityFrameworkCore;
using MarketDataApi.Models;
using Polly;
using Microsoft.AspNetCore.RateLimiting;
using Microsoft.AspNetCore.Mvc;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddMemoryCache();
builder.Services.AddRateLimiter(options =>
{
    options.AddFixedWindowLimiter("MarketPolicy", opt =>
    {
        opt.PermitLimit = 20;
        opt.Window = TimeSpan.FromSeconds(10); 
        opt.QueueLimit = 0; 
    });

    options.OnRejected = async (context, token) =>
    {
        context.HttpContext.Response.StatusCode = StatusCodes.Status429TooManyRequests;
        await context.HttpContext.Response.WriteAsJsonAsync(new { 
            error = "Too Many Requests", 
            message = "You reached the rate limit. Please wait before making more requests." 
        }, cancellationToken: token);
    };
});;

// Register API DB service
var connectionString = builder.Configuration.GetConnectionString("DefaultConnection");
builder.Services.AddHttpClient<CoinGeckoService>()
    .AddTransientHttpErrorPolicy(policyBuilder => 
        policyBuilder.WaitAndRetryAsync(3, tentativa => TimeSpan.FromSeconds(Math.Pow(2, tentativa)))
    );

builder.Services.AddHttpClient<BrapiService>()
    .AddTransientHttpErrorPolicy(policyBuilder => 
        policyBuilder.WaitAndRetryAsync(3, retryAttempt => TimeSpan.FromSeconds(Math.Pow(2, retryAttempt)))
    );

// Register Python Engine Service for Fundamentals
var marketBrainUrl = builder.Configuration["MarketBrain:BaseUrl"] ?? "http://localhost:8000";

builder.Services.AddHttpClient<MarketBrainService>(client =>
{
    client.BaseAddress = new Uri(marketBrainUrl); 
})
.AddTransientHttpErrorPolicy(policyBuilder => 
    policyBuilder.WaitAndRetryAsync(2, retryAttempt => TimeSpan.FromSeconds(1))
);
    
builder.Services.AddTransient<Func<string, IMarketDataService>>(serviceProvider => assetType =>
{
    if (assetType.ToLower() == "stock")
    {
        return serviceProvider.GetRequiredService<BrapiService>();
    }

    return serviceProvider.GetRequiredService<CoinGeckoService>();
});

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(connectionString));

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
    app.UseRateLimiter();
}

using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    db.Database.Migrate(); 
}

app.MapGet("/price/{assetType}/{symbol}", async (
    [FromServices] Func<string, IMarketDataService> serviceFactory,
    string assetType, 
    string symbol, 
    AppDbContext db) => 
{
    var normalizedAssetType = assetType.ToLowerInvariant();
    if (normalizedAssetType != "crypto" && normalizedAssetType != "stock")
    {
        return Results.BadRequest(new
        {
            message = $"Unsupported asset type '{assetType}'. Supported values are: 'crypto', 'stock'."
        });
    }

    var marketDataService = serviceFactory(normalizedAssetType); 

    var price = await marketDataService.GetPriceAsync(symbol);

    if (price == null) 
    {
        return Results.NotFound(new 
        { 
            message = $"Asset '{symbol.ToUpper()}' not found in the {normalizedAssetType} market.",
            suggestion = "Please check the ticker symbol and ensure you selected the correct market (Crypto vs B3)."
        });
    }

    var log = new SearchLog
    {
        CoinName = symbol,
        PriceUsd = price.Value,
        SearchDate = DateTime.UtcNow
    };

    db.SearchLogs.Add(log);
    await db.SaveChangesAsync(); 

    var currency = normalizedAssetType == "stock" ? "BRL" : "USD";

    return Results.Ok(new { 
        symbol = symbol.ToUpperInvariant(),
        assetType = normalizedAssetType,
        price,
        currency,
        timestamp = DateTime.UtcNow 
    });
})
.RequireRateLimiting("MarketPolicy");

app.MapGet("/price/{assetType}/{symbol}/history", async (
    string assetType, 
    string symbol, 
    [FromServices] Func<string, IMarketDataService> serviceFactory)
=> 
{
    var normalizedAssetType = assetType.ToLowerInvariant();
    if (normalizedAssetType != "crypto" && normalizedAssetType != "stock")
    {
        return Results.BadRequest(new
        {
            message = $"Unsupported asset type '{assetType}'. Supported values are: 'crypto', 'stock'."
        });
    }

    var marketDataService = serviceFactory(normalizedAssetType);
    var history = await marketDataService.GetHistoryAsync(symbol);
    if (history == null) return Results.NotFound(new {
        message = $"History for asset '{symbol.ToUpper()}' not found in the {normalizedAssetType} market.",
        suggestion = "Please check the ticker symbol and ensure you selected the correct market (Crypto vs B3)."
    });

    return Results.Ok(new {
        symbol = symbol.ToUpperInvariant(),
        assetType = normalizedAssetType,
        last_7_days = history,
    });
})
.RequireRateLimiting("MarketPolicy");

app.MapGet("/logs", async (AppDbContext db) => 
{
    var logs = await db.SearchLogs
        .OrderByDescending(log => log.SearchDate)
        .Take(10)
        .ToListAsync();

    return Results.Ok(logs);
});

app.MapGet("/fundamentals/{assetType}/{symbol}", async (
    string assetType, 
    string symbol, 
    MarketBrainService brainService,
    AppDbContext db) => 
{
    var normalizedType = assetType.ToLowerInvariant();
    var normalizedSymbol = symbol.ToUpperInvariant();
    
    if (normalizedType != "stock" && normalizedType != "fii")
    {
        return Results.BadRequest(new { message = $"Unsupported asset type '{assetType}'. Supported values are: 'stock', 'fii'." });
    }

    var existingRecord = await db.Fundamentals.FirstOrDefaultAsync(f => f.Ticker == normalizedSymbol);

    if (existingRecord != null && existingRecord.LastUpdatedAt > DateTime.UtcNow.AddHours(-24))
    {
        return Results.Ok(existingRecord);
    }

    var fundamentalsJson = await brainService.GetFundamentalsAsync(normalizedType, normalizedSymbol);

    if (fundamentalsJson == null)
    {
        if (existingRecord != null) return Results.Ok(existingRecord);

        return Results.NotFound(new { message = $"Fundamentals for asset '{normalizedSymbol}' not found." });
    }

    decimal? ParseDecimal(string key)
    {
        var node = fundamentalsJson[key];
        return node == null ? null : decimal.TryParse(node.ToString(), System.Globalization.CultureInfo.InvariantCulture, out var result) ? result : null;
    }

    int? ParseInt(string key)
    {
        var node = fundamentalsJson[key];
        return node == null ? null : int.TryParse(node.ToString(), out var result) ? result : null;
    }

    string? ParseString(string key) => fundamentalsJson[key]?.ToString();

    bool isNewRecord = false;
    if (existingRecord == null)
    {
        existingRecord = new FundamentalRecord { Ticker = normalizedSymbol };
        isNewRecord = true;
    }

    existingRecord.AssetType = normalizedType;
    existingRecord.SectorOrSegment = ParseString(normalizedType == "stock" ? "sector" : "segment");
    existingRecord.PriceToEarnings = ParseDecimal("p_l");
    existingRecord.PriceToBook = ParseDecimal("p_vp");
    existingRecord.DividendYield = ParseDecimal("dy");
    existingRecord.Roe = ParseDecimal("roe");
    existingRecord.NetMargin = ParseDecimal("net_margin");
    existingRecord.DebtToEbitda = ParseDecimal("debt_ebitda");
    existingRecord.Cagr5y = ParseDecimal("cagr_5y");
    
    existingRecord.FiiType = ParseString("tipo_fii");
    existingRecord.Vacancy = ParseDecimal("vacancy");
    existingRecord.PropertiesCount = ParseInt("properties_count");
    existingRecord.ShareholdersCount = ParseDecimal("numero_cotistas");
    
    existingRecord.LastUpdatedAt = DateTime.UtcNow;

    if (isNewRecord)
        db.Fundamentals.Add(existingRecord);
    else
        db.Fundamentals.Update(existingRecord);

    await db.SaveChangesAsync();

        var responsePayload = new Dictionary<string, object?>
    {
        { "ticker", existingRecord.Ticker },
        { "sector", existingRecord.AssetType == "stock" ? existingRecord.SectorOrSegment : null },
        { "segment", existingRecord.AssetType == "fii" ? existingRecord.SectorOrSegment : null },
        { "p_l", existingRecord.PriceToEarnings },
        { "p_vp", existingRecord.PriceToBook },
        { "dy", existingRecord.DividendYield },
        { "roe", existingRecord.Roe },
        { "net_margin", existingRecord.NetMargin },
        { "debt_ebitda", existingRecord.DebtToEbitda },
        { "cagr_5y", existingRecord.Cagr5y },
        { "tipo_fii", existingRecord.FiiType },
        { "vacancy", existingRecord.Vacancy },
        { "properties_count", existingRecord.PropertiesCount },
        { "numero_cotistas", existingRecord.ShareholdersCount },
        { "last_updated_at", existingRecord.LastUpdatedAt },
        { "largest_tenant_pct", null },
        { "avg_contract_term", null },
        { "contract_type", null },
        { "inadimplencia", null },
        { "%_cdi_ipca", null },
        { "cri_ratings", null },
        { "cash_available", null }
    };

    return Results.Ok(responsePayload);
})
.RequireRateLimiting("MarketPolicy");

app.Run();

// Expose the Program class to the Test Project
public partial class Program { }