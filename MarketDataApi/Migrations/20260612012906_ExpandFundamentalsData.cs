using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace MarketDataApi.Migrations
{
    /// <inheritdoc />
    public partial class ExpandFundamentalsData : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.RenameColumn(
                name: "Cagr5y",
                table: "Fundamentals",
                newName: "RevenueCagr5y");

            migrationBuilder.AddColumn<decimal>(
                name: "DailyLiquidity",
                table: "Fundamentals",
                type: "numeric",
                nullable: true);

            migrationBuilder.AddColumn<decimal>(
                name: "EvEbit",
                table: "Fundamentals",
                type: "numeric",
                nullable: true);

            migrationBuilder.AddColumn<decimal>(
                name: "EvEbitda",
                table: "Fundamentals",
                type: "numeric",
                nullable: true);

            migrationBuilder.AddColumn<decimal>(
                name: "LastDividend",
                table: "Fundamentals",
                type: "numeric",
                nullable: true);

            migrationBuilder.AddColumn<decimal>(
                name: "MarketCap",
                table: "Fundamentals",
                type: "numeric",
                nullable: true);

            migrationBuilder.AddColumn<decimal>(
                name: "NetWorth",
                table: "Fundamentals",
                type: "numeric",
                nullable: true);

            migrationBuilder.AddColumn<decimal>(
                name: "ProfitCagr5y",
                table: "Fundamentals",
                type: "numeric",
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "DailyLiquidity",
                table: "Fundamentals");

            migrationBuilder.DropColumn(
                name: "EvEbit",
                table: "Fundamentals");

            migrationBuilder.DropColumn(
                name: "EvEbitda",
                table: "Fundamentals");

            migrationBuilder.DropColumn(
                name: "LastDividend",
                table: "Fundamentals");

            migrationBuilder.DropColumn(
                name: "MarketCap",
                table: "Fundamentals");

            migrationBuilder.DropColumn(
                name: "NetWorth",
                table: "Fundamentals");

            migrationBuilder.DropColumn(
                name: "ProfitCagr5y",
                table: "Fundamentals");

            migrationBuilder.RenameColumn(
                name: "RevenueCagr5y",
                table: "Fundamentals",
                newName: "Cagr5y");
        }
    }
}
