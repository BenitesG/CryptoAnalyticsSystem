using MarketDataApi.Models;
using Microsoft.EntityFrameworkCore;

namespace MarketDataApi.Data;

public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    public DbSet<SearchLog> SearchLogs { get; set; }
    public DbSet<FundamentalRecord> Fundamentals { get; set; }
    
    public DbSet<User> Users { get; set; }
    public DbSet<UserAsset> UserAssets { get; set; }
}