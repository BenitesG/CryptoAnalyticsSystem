using Moq;
using Moq.Protected;
using System.Net;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Configuration;
using MarketDataApi.Services;

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
    }
}