using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace MarketDataApi.Models;

public class UserAsset
{
    [Key]
    public Guid Id { get; set; } = Guid.NewGuid();

    [Required]
    public Guid UserId { get; set; }

    [Required]
    [MaxLength(10)]
    public string Ticker { get; set; } = string.Empty;

    [Required]
    [Column(TypeName = "decimal(18,4)")]
    public decimal Quantity { get; set; }

    [Required]
    [Column(TypeName = "decimal(18,4)")]
    public decimal AveragePrice { get; set; } // Used to calculate P&L (Profit and Loss) and Yield on Cost

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    // Foreign Key Navigation Property
    [ForeignKey("UserId")]
    public User? User { get; set; }
}