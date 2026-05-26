using System.Net;
using MarketDataApi.Services;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Logging;
using Moq;
using Moq.Protected;

namespace MarketDataApi.Tests
{
    public class MarketBrainServiceTests
    {
        [Fact]
        public async Task GetFundamentalsAsync_ShouldReturnNull_WhenApiReturnsNotFound()
        {
            var handlerMock = new Mock<HttpMessageHandler>();
            handlerMock.Protected()
                .Setup<Task<HttpResponseMessage>>(
                    "SendAsync",
                    ItExpr.IsAny<HttpRequestMessage>(),
                    ItExpr.IsAny<CancellationToken>())
                .ReturnsAsync(new HttpResponseMessage
                {
                    StatusCode = HttpStatusCode.NotFound
                });

            var httpClient = new HttpClient(handlerMock.Object)
            {
                BaseAddress = new Uri("http://localhost:8000")
            };
            var cache = new MemoryCache(new MemoryCacheOptions());
            var loggerMock = new Mock<ILogger<MarketBrainService>>();
            var service = new MarketBrainService(httpClient, cache, loggerMock.Object);

            var result = await service.GetFundamentalsAsync("stock", "petr4");

            Assert.Null(result);
        }

        [Fact]
        public async Task GetFundamentalsAsync_ShouldThrow_WhenApiReturnsServerError()
        {
            var handlerMock = new Mock<HttpMessageHandler>();
            handlerMock.Protected()
                .Setup<Task<HttpResponseMessage>>(
                    "SendAsync",
                    ItExpr.IsAny<HttpRequestMessage>(),
                    ItExpr.IsAny<CancellationToken>())
                .ReturnsAsync(new HttpResponseMessage
                {
                    StatusCode = HttpStatusCode.InternalServerError
                });

            var httpClient = new HttpClient(handlerMock.Object)
            {
                BaseAddress = new Uri("http://localhost:8000")
            };
            var cache = new MemoryCache(new MemoryCacheOptions());
            var loggerMock = new Mock<ILogger<MarketBrainService>>();
            var service = new MarketBrainService(httpClient, cache, loggerMock.Object);

            await Assert.ThrowsAsync<HttpRequestException>(() => service.GetFundamentalsAsync("stock", "petr4"));
        }

        [Fact]
        public async Task GetFundamentalsAsync_ShouldUseCache_OnRepeatedRequests()
        {
            var handlerMock = new Mock<HttpMessageHandler>();
            handlerMock.Protected()
                .Setup<Task<HttpResponseMessage>>(
                    "SendAsync",
                    ItExpr.IsAny<HttpRequestMessage>(),
                    ItExpr.IsAny<CancellationToken>())
                .ReturnsAsync(new HttpResponseMessage
                {
                    StatusCode = HttpStatusCode.OK,
                    Content = new StringContent("""{"ticker":"PETR4"}""")
                });

            var httpClient = new HttpClient(handlerMock.Object)
            {
                BaseAddress = new Uri("http://localhost:8000")
            };
            var cache = new MemoryCache(new MemoryCacheOptions());
            var loggerMock = new Mock<ILogger<MarketBrainService>>();
            var service = new MarketBrainService(httpClient, cache, loggerMock.Object);

            var first = await service.GetFundamentalsAsync("stock", "petr4");
            var second = await service.GetFundamentalsAsync("stock", "petr4");

            Assert.NotNull(first);
            Assert.Same(first, second);
            handlerMock.Protected().Verify(
                "SendAsync",
                Times.Once(),
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>());
        }
    }
}
