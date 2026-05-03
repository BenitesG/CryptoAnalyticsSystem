using MarketDataApi.Services;
using MarketDataApi.Data;
using Microsoft.EntityFrameworkCore;
using MarketDataApi.Models;
using Polly;
using Microsoft.AspNetCore.Mvc;

// See https://aka.ms/new-console-template for more information
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddMemoryCache();

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
});

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
});

app.MapGet("/logs", async (AppDbContext db) => 
{
    var logs = await db.SearchLogs
        .OrderByDescending(log => log.SearchDate)
        .Take(10)
        .ToListAsync();

    return Results.Ok(logs);
});

app.Run();