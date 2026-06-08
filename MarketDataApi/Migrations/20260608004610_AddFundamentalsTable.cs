using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace MarketDataApi.Migrations
{
    /// <inheritdoc />
    public partial class AddFundamentalsTable : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "Fundamentals",
                columns: table => new
                {
                    Ticker = table.Column<string>(type: "text", nullable: false),
                    AssetType = table.Column<string>(type: "text", nullable: false),
                    SectorOrSegment = table.Column<string>(type: "text", nullable: true),
                    PriceToEarnings = table.Column<decimal>(type: "numeric", nullable: true),
                    PriceToBook = table.Column<decimal>(type: "numeric", nullable: true),
                    DividendYield = table.Column<decimal>(type: "numeric", nullable: true),
                    Roe = table.Column<decimal>(type: "numeric", nullable: true),
                    NetMargin = table.Column<decimal>(type: "numeric", nullable: true),
                    DebtToEbitda = table.Column<decimal>(type: "numeric", nullable: true),
                    Cagr5y = table.Column<decimal>(type: "numeric", nullable: true),
                    FiiType = table.Column<string>(type: "text", nullable: true),
                    Vacancy = table.Column<decimal>(type: "numeric", nullable: true),
                    PropertiesCount = table.Column<int>(type: "integer", nullable: true),
                    ShareholdersCount = table.Column<decimal>(type: "numeric", nullable: true),
                    LastUpdatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Fundamentals", x => x.Ticker);
                });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "Fundamentals");
        }
    }
}
