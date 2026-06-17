using System.ComponentModel.DataAnnotations;

namespace MarketDataApi.Models;

public class User
{
    [Key]
    public Guid Id { get; set; } = Guid.NewGuid();

    [Required]
    [MaxLength(50)]
    public string Username { get; set; } = string.Empty;

    [Required]
    public string PasswordHash { get; set; } = string.Empty; // Salted and hashed password for security

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    // Navigation property: One user can have many assets
    public ICollection<UserAsset> Assets { get; set; } = new List<UserAsset>();
}