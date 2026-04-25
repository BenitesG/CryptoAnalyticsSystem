using CryptoDataApi.Services;
using CryptoDataApi.Data;
using Microsoft.EntityFrameworkCore;
using CryptoDataApi.Models;

// See https://aka.ms/new-console-template for more information
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddMemoryCache();

// Register API DB service
var connectionString = builder.Configuration.GetConnectionString("DefaultConnection");
builder.Services.AddHttpClient<CoinGeckoService>();
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(connectionString));

var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    db.Database.Migrate(); 
}

app.MapGet("/price/{coin}", async (CoinGeckoService cryptoService, string coin, AppDbContext db) => 
{
    var price = await cryptoService.GetPriceAsync(coin);

    if (price == null) 
    {
        return Results.NotFound(new { message = "Não foi possível obter o preço agora." });
    }

    var log = new SearchLog
    {
        CoinName = coin,
        PriceUsd = price.Value,
        SearchDate = DateTime.UtcNow
    };

    db.SearchLogs.Add(log);
    await db.SaveChangesAsync(); 

    return Results.Ok(new { 
        coin = coin,
        price_usd = price,
        timestamp = DateTime.UtcNow 
    });
});

app.MapGet("/price/{coin}/history", async (string coin, CoinGeckoService cryptoservice) => 
{
    var history = await cryptoservice.GetHistoryAsync(coin);
    if (history == null) return Results.NotFound("Histórico não encontrado.");
    

    return Results.Ok(new {
        coin = coin,
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