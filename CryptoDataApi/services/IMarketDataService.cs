namespace CryptoDataApi.Services
{
    public interface IMarketDataService
    {
        Task<decimal?> GetPriceAsync(string ticker);
        Task<object?> GetHistoryAsync(string ticker);
    }
}