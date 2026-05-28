using System.Net;
using System.Net.Http.Json;
using System.Text.Json.Nodes;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Http;
using Moq;
using Moq.Protected;

namespace MarketDataApi.Tests;

public class FundamentalsEndpointTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly WebApplicationFactory<Program> _factory;

    public FundamentalsEndpointTests(WebApplicationFactory<Program> factory)
    {
        _factory = factory;
    }

    private WebApplicationFactory<Program> GetConfiguredFactory()
    {
        return _factory.WithWebHostBuilder(builder =>
        {
            builder.ConfigureAppConfiguration((context, config) =>
            {
                config.AddInMemoryCollection(new Dictionary<string, string?>
                {
                    { "MarketBrain:BaseUrl", "http://localhost:8000" },
                    { "Brapi:BaseUrl", "https://brapi.dev/api" },
                    { "Brapi:BrapiApiKey", "FAKE_TEST_KEY" },
                    { "ConnectionStrings:DefaultConnection", "Host=localhost;Database=testdb;Username=postgres;Password=postgres" }
                });
            });
        });
    }

    [Fact]
    public async Task GetFundamentals_ShouldReturnOk_AndProxyPythonData()
    {
        // 1. ARRANGE
        var fakePythonResponse = """
        {
            "ticker": "TAEE11",
            "p_l": 8.47,
            "dy": 8.49,
            "sector": "Utilidade Pública"
        }
        """;

        var handlerMock = new Mock<HttpMessageHandler>();
        handlerMock.Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                // O Pulo do Gato: ToLower() garante que vai dar Match!
                ItExpr.Is<HttpRequestMessage>(req => req.RequestUri!.ToString().ToLower().Contains("/fundamentals/stock/taee11")),
                ItExpr.IsAny<CancellationToken>())
            .ReturnsAsync((HttpRequestMessage request, CancellationToken token) => new HttpResponseMessage
            {
                StatusCode = HttpStatusCode.OK,
                Content = new StringContent(fakePythonResponse, System.Text.Encoding.UTF8, "application/json"),
                RequestMessage = request
            });

        var client = GetConfiguredFactory().WithWebHostBuilder(builder =>
        {
            builder.ConfigureServices(services =>
            {
                // A forma mais segura de forçar um Mock em um HttpClient tipado no .NET 8
                services.ConfigureAll<HttpClientFactoryOptions>(options =>
                {
                    options.HttpMessageHandlerBuilderActions.Add(b => b.PrimaryHandler = handlerMock.Object);
                });
            });
        }).CreateClient();

        // 2. ACT
        var response = await client.GetAsync("/fundamentals/stock/taee11");

        // Capturamos o texto do erro caso aconteça para facilitar o debug!
        var errorContent = await response.Content.ReadAsStringAsync();

        // 3. ASSERT
        Assert.True(response.StatusCode == HttpStatusCode.OK, $"Esperado OK, mas retornou {response.StatusCode}. Detalhe: {errorContent}");

        var jsonResult = await response.Content.ReadFromJsonAsync<JsonObject>();
        Assert.NotNull(jsonResult);
        Assert.Equal("TAEE11", jsonResult["ticker"]?.ToString());
        Assert.Equal("8.47", jsonResult["p_l"]?.ToString());
    }

    [Fact]
    public async Task GetFundamentals_ShouldReturnBadRequest_WhenAssetTypeIsInvalid()
    {
        // ARRANGE
        var client = GetConfiguredFactory().CreateClient();

        // ACT
        var response = await client.GetAsync("/fundamentals/crypto/bitcoin");

        // ASSERT
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }
}