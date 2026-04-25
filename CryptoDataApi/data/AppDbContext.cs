using CryptoDataApi.Models; 
using Microsoft.EntityFrameworkCore;

namespace CryptoDataApi.Data
{   // DB Context
    public class AppDbContext : DbContext
    {
        public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

        public DbSet<SearchLog> SearchLogs { get; set; }
    }
}