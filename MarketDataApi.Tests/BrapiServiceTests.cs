using Moq;
using Moq.Protected;
using System.Net;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Configuration;
using MarketDataApi.Services;
using System.Text.Json;

namespace MarketDataApi.Tests
{
    public class BrapiServiceTests
    {
        [Fact]
        public async Task GetPriceAsync_ShouldReturnPrice_WhenApiReturnsSuccess()
        {
            var ticker = "PETR4";
            var fakeJson = "{\"results\": [{\"regularMarketPrice\": 45.50}]}";

            var handlerMock = new Mock<HttpMessageHandler>();
            handlerMock.Protected()
                .Setup<Task<HttpResponseMessage>>(
                    "SendAsync",
                    ItExpr.IsAny<HttpRequestMessage>(),
                    ItExpr.IsAny<CancellationToken>()
                )
                .ReturnsAsync(new HttpResponseMessage
                {
                    StatusCode = HttpStatusCode.OK,
                    Content = new StringContent(fakeJson)
                });

            var httpClient = new HttpClient(handlerMock.Object);

            var configMock = new Mock<IConfiguration>();
            configMock.Setup(c => c["Brapi:BrapiApiKey"]).Returns("FALSE_KEY");
            configMock.Setup(c => c["Brapi:BaseUrl"]).Returns("https://brapi.dev/api");

            var cache = new MemoryCache(new MemoryCacheOptions());
            var loggerMock = new Mock<ILogger<BrapiService>>();

            var brapiService = new BrapiService(httpClient, cache, loggerMock.Object, configMock.Object);

            var result = await brapiService.GetPriceAsync(ticker);

            Assert.NotNull(result);
            Assert.Equal(45.50m, result);

        }
        [Fact]
        public async Task GetPriceAsync_ShouldReturnNull_WhenApiReturnsNotFound()
        {
            var ticker = "PETR4";
            var fakeJson = "{\"results\": [{\"regularMarketPrice\": null}]}";

            var handlerMock = new Mock<HttpMessageHandler>();
            handlerMock.Protected()
                .Setup<Task<HttpResponseMessage>>(
                    "SendAsync",
                    ItExpr.IsAny<HttpRequestMessage>(),
                    ItExpr.IsAny<CancellationToken>()
                )
                .ReturnsAsync(new HttpResponseMessage
                {
                    StatusCode = HttpStatusCode.NotFound,
                    Content = new StringContent(fakeJson)
                });

            var httpClient = new HttpClient(handlerMock.Object);

            var configMock = new Mock<IConfiguration>();
            configMock.Setup(c => c["Brapi:BrapiApiKey"]).Returns("FALSE_KEY");
            configMock.Setup(c => c["Brapi:BaseUrl"]).Returns("https://brapi.dev/api");

            var cache = new MemoryCache(new MemoryCacheOptions());
            var loggerMock = new Mock<ILogger<BrapiService>>();

            var brapiService = new BrapiService(httpClient, cache, loggerMock.Object, configMock.Object);

            var result = await brapiService.GetPriceAsync(ticker);

            Assert.Null(result);

        }

        [Fact]
        public async Task GetHistoryAsync_ShouldMapActionSignal_FromPythonAnalysis()
        {
            var ticker = "PETR4";
            var brapiHistoryJson = """
            {
              "results": [
                {
                  "symbol": "PETR4",
                  "historicalDataPrice": [
                    { "date": 1710000000, "close": 35.20 },
                    { "date": 1710086400, "close": 36.10 },
                    { "date": 1710172800, "close": 37.50 }
                  ]
                }
              ]
            }
            """;
            var pythonAnalysisJson = """
            {
              "trend": "UP",
              "percentage_change": 6.53,
              "volatility": 0.95,
              "historical_prices": [35.20, 36.10, 37.50],
              "action_signal": "BUY"
            }
            """;

            var handlerMock = new Mock<HttpMessageHandler>();

            handlerMock.Protected()
                .Setup<Task<HttpResponseMessage>>(
                    "SendAsync",
                    ItExpr.Is<HttpRequestMessage>(req =>
                        req.Method == HttpMethod.Get &&
                        req.RequestUri != null &&
                        req.RequestUri.ToString().Contains("/quote/PETR4")),
                    ItExpr.IsAny<CancellationToken>())
                .ReturnsAsync(new HttpResponseMessage
                {
                    StatusCode = HttpStatusCode.OK,
                    Content = new StringContent(brapiHistoryJson)
                });

            handlerMock.Protected()
                .Setup<Task<HttpResponseMessage>>(
                    "SendAsync",
                    ItExpr.Is<HttpRequestMessage>(req =>
                        req.Method == HttpMethod.Post &&
                        req.RequestUri != null &&
                        req.RequestUri.ToString() == "http://localhost:8000/analyze"),
                    ItExpr.IsAny<CancellationToken>())
                .ReturnsAsync(new HttpResponseMessage
                {
                    StatusCode = HttpStatusCode.OK,
                    Content = new StringContent(pythonAnalysisJson)
                });

            var httpClient = new HttpClient(handlerMock.Object);

            var configMock = new Mock<IConfiguration>();
            configMock.Setup(c => c["Brapi:BrapiApiKey"]).Returns("FALSE_KEY");
            configMock.Setup(c => c["Brapi:BaseUrl"]).Returns("https://brapi.dev/api");

            var cache = new MemoryCache(new MemoryCacheOptions());
            var loggerMock = new Mock<ILogger<BrapiService>>();

            var brapiService = new BrapiService(httpClient, cache, loggerMock.Object, configMock.Object);

            var result = await brapiService.GetHistoryAsync(ticker);

            Assert.NotNull(result);

            var json = JsonSerializer.Serialize(result);
            using var doc = JsonDocument.Parse(json);

            Assert.Equal("BUY", doc.RootElement.GetProperty("action_signal").GetString());
        }
    }
}
