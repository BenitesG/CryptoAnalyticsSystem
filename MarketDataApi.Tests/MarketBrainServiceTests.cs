using System.Net;
using MarketDataApi.Services;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Logging;
using Moq;
using MarketDataApi.Models;
using Moq.Protected;
using Microsoft.Extensions.Caching.Distributed;

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
        [Fact]
        public async Task AnalyzePortfolioAsync_ShouldReturnAnalysis_WhenApiReturnsOk()
        {
            // Arrange
            var handlerMock = new Mock<HttpMessageHandler>();
            var responseJson = """{"status":"success","analysis":"Mocked AI analysis result"}""";

            handlerMock.Protected()
                .Setup<Task<HttpResponseMessage>>(
                    "SendAsync",
                    ItExpr.IsAny<HttpRequestMessage>(),
                    ItExpr.IsAny<CancellationToken>())
                .ReturnsAsync(new HttpResponseMessage
                {
                    StatusCode = HttpStatusCode.OK,
                    Content = new StringContent(responseJson)
                });

            var httpClient = new HttpClient(handlerMock.Object)
            {
                BaseAddress = new Uri("http://localhost:8000")
            };
            var cache = new MemoryCache(new MemoryCacheOptions());
            var loggerMock = new Mock<ILogger<MarketBrainService>>();
            var service = new MarketBrainService(httpClient, cache, loggerMock.Object);

            var assets = new List<AssetAnalysisInput>
            {
                new("WEGE3", 100, 35.50m, 38.00m, 250.00m)
            };

            // Act
            var result = await service.AnalyzePortfolioAsync(assets);

            // Assert
            Assert.NotNull(result);
            Assert.Equal("success", result?.Status);
            Assert.Equal("Mocked AI analysis result", result?.Analysis);
        }

        [Fact]
        public async Task AnalyzePortfolioAsync_ShouldThrow_WhenApiReturnsServerError()
        {
            // Arrange
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

            var assets = new List<AssetAnalysisInput>
            {
                new("WEGE3", 100, 35.50m, 38.00m, 250.00m)
            };

            // Act & Assert
            await Assert.ThrowsAsync<HttpRequestException>(() => service.AnalyzePortfolioAsync(assets));
        }

        [Fact]
        public async Task AnalyzePortfolioAsync_ShouldReturnCachedAnalysis_WithoutCallingHttp_WhenCacheHit()
        {
            var handlerMock = new Mock<HttpMessageHandler>();
            var httpClient = new HttpClient(handlerMock.Object)
            {
                BaseAddress = new Uri("http://localhost:8000")
            };
            var memoryCache = new MemoryCache(new MemoryCacheOptions());
            var loggerMock = new Mock<ILogger<MarketBrainService>>();

            var distributedCacheMock = new Mock<IDistributedCache>();
            
            var cachedJson = """{"status":"success","analysis":"This is cached AI analysis"}""";
            var cachedBytes = System.Text.Encoding.UTF8.GetBytes(cachedJson);

            distributedCacheMock
                .Setup(c => c.GetAsync(It.IsAny<string>(), It.IsAny<CancellationToken>()))
                .ReturnsAsync(cachedBytes);

            var service = new MarketBrainService(
                httpClient, 
                memoryCache, 
                distributedCacheMock.Object, 
                loggerMock.Object
            );

            var assets = new List<AssetAnalysisInput>
            {
                new("WEGE3", 100, 35.50m, 38.00m, 250.00m)
            };

            var result = await service.AnalyzePortfolioWithCacheAsync(assets); 

            Assert.NotNull(result);
            Assert.Equal("This is cached AI analysis", result?.Analysis);
            
            handlerMock.Protected().Verify(
                "SendAsync",
                Times.Never(), // Verifica se foi chamado ZERO vezes
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>()
            );
        }
    }
}

