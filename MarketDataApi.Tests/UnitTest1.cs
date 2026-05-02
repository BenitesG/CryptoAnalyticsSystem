using MarketDataApi.Models; // Importa os models da sua API

namespace MarketDataApi.Tests;

public class SearchLogTests
{
    [Fact] // Isso avisa o C# que esta função é um Teste Unitário
    public void SearchLog_Should_StoreDataCorrectly()
    {
        // Padrão global de testes: AAA (Arrange, Act, Assert)

        // 1. ARRANGE (Preparar o terreno)
        var log = new SearchLog();
        var dataAtual = DateTime.UtcNow;

        // 2. ACT (Agir)
        log.CoinName = "bitcoin";
        log.PriceUsd = 50000.50m;
        log.SearchDate = dataAtual;

        // 3. ASSERT (Verificar/Garantir)
        Assert.Equal("bitcoin", log.CoinName);
        Assert.Equal(50000.50m, log.PriceUsd);
        Assert.Equal(dataAtual, log.SearchDate);
    }
}