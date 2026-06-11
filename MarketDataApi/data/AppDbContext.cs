using MarketDataApi.Models; 
using Microsoft.EntityFrameworkCore;


namespace MarketDataApi.Data
{   // DB Context
    public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    public DbSet<SearchLog> SearchLogs { get; set; }
    
    public DbSet<FundamentalRecord> Fundamentals { get; set; }
}}