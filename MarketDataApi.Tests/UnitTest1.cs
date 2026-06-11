using MarketDataApi.Models;

namespace MarketDataApi.Tests;

public class SearchLogTests
{
    [Fact] 
    public void SearchLog_Should_StoreDataCorrectly()
    {

        // 1. ARRANGE 
        var log = new SearchLog();
        var dataAtual = DateTime.UtcNow;

        // 2. ACT 
        log.CoinName = "bitcoin";
        log.PriceUsd = 50000.50m;
        log.SearchDate = dataAtual;

        // 3. ASSERT 
        Assert.Equal("bitcoin", log.CoinName);
        Assert.Equal(50000.50m, log.PriceUsd);
        Assert.Equal(dataAtual, log.SearchDate);
    }
}