# Build (SDK)
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# Copy csproj and restore as distinct layers
COPY ["MarketDataApi.csproj", "./"]
RUN dotnet restore "MarketDataApi.csproj"

# Copy the rest of the code and publish
COPY . .
RUN dotnet publish "MarketDataApi.csproj" -c Release -o /app/publish /p:UseAppHost=false

# Final (Runtime)
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app
COPY --from=build /app/publish .

# PORT
EXPOSE 8080

# Run API
ENTRYPOINT ["dotnet", "MarketDataApi.dll"]