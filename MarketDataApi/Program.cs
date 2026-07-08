using MarketDataApi.Services;
using MarketDataApi.Data;
using Microsoft.EntityFrameworkCore;
using MarketDataApi.Models;
using Polly;
using Microsoft.AspNetCore.RateLimiting;
using Microsoft.AspNetCore.Mvc;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddMemoryCache();
builder.Services.AddStackExchangeRedisCache(options =>
{
    options.Configuration = builder.Configuration.GetValue<string>("Redis:ConnectionString") ?? "cache:6379";
});
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
    
    // 1. Route validation
    if (normalizedType != "stock" && normalizedType != "fii")
    {
        return Results.BadRequest(new { message = $"Unsupported asset type '{assetType}'. Supported values are: 'stock', 'fii'." });
    }

    // 2. Try fetching from Database Cache first
    var existingRecord = await db.Fundamentals.FirstOrDefaultAsync(f => f.Ticker == normalizedSymbol);

    // If cache is fresh (less than 24 hours), return the mapped snake_case JSON
    if (existingRecord != null && existingRecord.LastUpdatedAt > DateTime.UtcNow.AddHours(-24))
    {
        var cachedPayload = new Dictionary<string, object?>
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
            
            // New cached fields
            { "market_cap", existingRecord.MarketCap },
            { "ev_ebit", existingRecord.EvEbit },
            { "ev_ebitda", existingRecord.EvEbitda },
            { "cagr_revenue", existingRecord.RevenueCagr5y },
            { "cagr_profit", existingRecord.ProfitCagr5y },
            { "tipo_fii", existingRecord.FiiType },
            { "vacancy", existingRecord.Vacancy },
            { "properties_count", existingRecord.PropertiesCount },
            { "numero_cotistas", existingRecord.ShareholdersCount },
            { "liquidity", existingRecord.DailyLiquidity },
            { "net_worth", existingRecord.NetWorth },
            { "last_dividend", existingRecord.LastDividend },
            { "last_updated_at", existingRecord.LastUpdatedAt },
            
            // Placeholders for visual consistency on frontend
            { "largest_tenant_pct", null },
            { "avg_contract_term", null },
            { "contract_type", null },
            { "inadimplencia", null },
            { "%_cdi_ipca", null },
            { "cri_ratings", null },
            { "cash_available", null }
        };
        return Results.Ok(cachedPayload);
    }

    // 3. Cache Miss: Fetch fresh data from Python Engine
    var fundamentalsJson = await brainService.GetFundamentalsAsync(normalizedType, normalizedSymbol);

    if (fundamentalsJson == null)
    {
        // Resiliency Fallback: Return stale DB data if Python is down
        if (existingRecord != null) return Results.Ok(existingRecord);
        return Results.NotFound(new { message = $"Fundamentals for asset '{normalizedSymbol}' not found." });
    }

    // Helpers to safely parse JSON into SQL-compatible types
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

    // 4. UPSERT (Update or Insert) mapping
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
    
    // Map New Stock Fields
    existingRecord.MarketCap = ParseDecimal("market_cap");
    existingRecord.EvEbit = ParseDecimal("ev_ebit");
    existingRecord.EvEbitda = ParseDecimal("ev_ebitda");
    existingRecord.RevenueCagr5y = ParseDecimal("cagr_revenue");
    existingRecord.ProfitCagr5y = ParseDecimal("cagr_profit");

    existingRecord.FiiType = ParseString("tipo_fii");
    existingRecord.Vacancy = ParseDecimal("vacancy");
    existingRecord.PropertiesCount = ParseInt("properties_count");
    existingRecord.ShareholdersCount = ParseDecimal("numero_cotistas");

    // Map New FII Fields
    existingRecord.DailyLiquidity = ParseDecimal("liquidity");
    existingRecord.NetWorth = ParseDecimal("net_worth");
    existingRecord.LastDividend = ParseDecimal("last_dividend");
    
    existingRecord.LastUpdatedAt = DateTime.UtcNow;

    // Save changes to PostgreSQL
    if (isNewRecord)
        db.Fundamentals.Add(existingRecord);
    else
        db.Fundamentals.Update(existingRecord);

    await db.SaveChangesAsync();

    // 5. Build final DTO response payload
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
        
        // Include new fields in JSON output
        { "market_cap", existingRecord.MarketCap },
        { "ev_ebit", existingRecord.EvEbit },
        { "ev_ebitda", existingRecord.EvEbitda },
        { "cagr_revenue", existingRecord.RevenueCagr5y },
        { "cagr_profit", existingRecord.ProfitCagr5y },
        
        { "tipo_fii", existingRecord.FiiType },
        { "vacancy", existingRecord.Vacancy },
        { "properties_count", existingRecord.PropertiesCount },
        { "numero_cotistas", existingRecord.ShareholdersCount },
        
        { "liquidity", existingRecord.DailyLiquidity },
        { "net_worth", existingRecord.NetWorth },
        { "last_dividend", existingRecord.LastDividend },
        { "last_updated_at", existingRecord.LastUpdatedAt },
        
        // Placeholders to maintain UI consistency
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

// ==========================================
// USER AUTHENTICATION ENDPOINTS
// ==========================================

// Register a new user securely hashing the password
app.MapPost("/users/register", async (RegisterRequest request, AppDbContext db) =>
{
    if (string.IsNullOrWhiteSpace(request.Username) || string.IsNullOrWhiteSpace(request.Password))
    {
        return Results.BadRequest(new { message = "Username and password are required." });
    }

    var normalizedUsername = request.Username.Trim().ToLowerInvariant();
    var userExists = await db.Users.AnyAsync(u => u.Username.ToLower() == normalizedUsername);
    
    if (userExists)
    {
        return Results.Conflict(new { message = "Username is already taken." });
    }

    var user = new User
    {
        Username = request.Username.Trim(),
        PasswordHash = BCrypt.Net.BCrypt.HashPassword(request.Password) // Secure hashing via BCrypt
    };

    db.Users.Add(user);
    await db.SaveChangesAsync();

    return Results.Created($"/users/{user.Id}", new { id = user.Id, username = user.Username });
});

// Login endpoint verifying the hashed password
app.MapPost("/users/login", async (LoginRequest request, AppDbContext db) =>
{
    var normalizedUsername = request.Username.Trim().ToLowerInvariant();
    var user = await db.Users.FirstOrDefaultAsync(u => u.Username.ToLower() == normalizedUsername);
    
    if (user == null || !BCrypt.Net.BCrypt.Verify(request.Password, user.PasswordHash))
    {
        return Results.Unauthorized();
    }

    return Results.Ok(new { id = user.Id, username = user.Username });
});

// ==========================================
// PORTFOLIO MANAGEMENT ENDPOINTS
// ==========================================

// Add or update an asset in user's portfolio calculating the Weighted Average Price
app.MapPost("/portfolios/add", async (AddAssetRequest request, AppDbContext db) =>
{
    var userExists = await db.Users.AnyAsync(u => u.Id == request.UserId);
    if (!userExists) return Results.NotFound(new { message = "User not found." });

    var normalizedTicker = request.Ticker.Trim().ToUpperInvariant();

    var existingAsset = await db.UserAssets
        .FirstOrDefaultAsync(a => a.UserId == request.UserId && a.Ticker == normalizedTicker);

    if (existingAsset == null)
    {
        // First buy: Save exactly what was sent
        var newAsset = new UserAsset
        {
            UserId = request.UserId,
            Ticker = normalizedTicker,
            Quantity = request.Quantity,
            AveragePrice = request.AveragePrice
        };
        db.UserAssets.Add(newAsset);
    }
    else
    {
        // Subsequent buy: Recalculate Weighted Average Price (Real Financial Engineering)
        decimal oldQty = existingAsset.Quantity;
        decimal oldAvg = existingAsset.AveragePrice;
        decimal newQty = oldQty + request.Quantity;

        if (newQty > 0)
        {
            decimal newAvg = ((oldQty * oldAvg) + (request.Quantity * request.AveragePrice)) / newQty;
            existingAsset.Quantity = newQty;
            existingAsset.AveragePrice = Math.Round(newAvg, 4); // Standardize to 4 decimal places
        }
        db.UserAssets.Update(existingAsset);
    }

    await db.SaveChangesAsync();
    return Results.Ok(new { message = "Asset successfully added/updated in portfolio." });
});

// Retrieve the complete portfolio for a specific user
app.MapGet("/portfolios/{userId:guid}", async (Guid userId, AppDbContext db) =>
{
    var assets = await db.UserAssets
        .Where(a => a.UserId == userId)
        .Select(a => new {
            a.Id,
            a.Ticker,
            a.Quantity,
            a.AveragePrice,
            total_invested = Math.Round(a.Quantity * a.AveragePrice, 2)
        })
        .ToListAsync();

    return Results.Ok(assets);
});

app.MapPost("/portfolios/{userId}/analyze-ai", async (
    Guid userId, // Mudamos de string para Guid aqui!
    [FromServices] AppDbContext db, 
    [FromServices] MarketBrainService brainService) =>
{
    // Agora a comparação funciona perfeitamente, pois ambos são do tipo Guid
    var userAssets = await db.UserAssets
        .Where(a => a.UserId == userId)
        .ToListAsync();

    if (!userAssets.Any())
    {
        return Results.BadRequest(new { message = "No assets found in this portfolio to analyze." });
    }

    // O restante do código permanece idêntico...
    var assetsPayload = userAssets.Select(asset => new AssetAnalysisInput(
        Ticker: asset.Ticker,
        Quantity: (decimal)asset.Quantity,
        AveragePrice: (decimal)asset.AveragePrice,
        LivePrice: (decimal)asset.AveragePrice,
        Pnl: 0.0m
    )).ToList();

    var analysisResult = await brainService.AnalyzePortfolioAsync(assetsPayload);

    if (analysisResult == null)
    {
        return Results.StatusCode(500);
    }

    return Results.Ok(analysisResult);
});

app.Run();

// --- PORTFOLIO & USER DTOs ---
public record RegisterRequest(string Username, string Password);
public record LoginRequest(string Username, string Password);
public record AddAssetRequest(Guid UserId, string Ticker, decimal Quantity, decimal AveragePrice);

// Expose the Program class to the Test Project
public partial class Program { }