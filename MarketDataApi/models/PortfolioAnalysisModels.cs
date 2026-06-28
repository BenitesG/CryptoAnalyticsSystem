namespace MarketDataApi.Models
{
    public record AssetAnalysisInput(
        string Ticker, 
        decimal Quantity, 
        decimal AveragePrice, 
        decimal LivePrice, 
        decimal Pnl
    );

    public record PortfolioAnalysisRequest(List<AssetAnalysisInput> Assets);

    public record PortfolioAnalysisResponse(string Status, string Analysis);
}