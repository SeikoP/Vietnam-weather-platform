let
    R2BaseUrl = "https://pub-74b943718d324227b2990146d782734c.r2.dev",
    AnalystPrefix = "v1/current/analyst/",
    LoadR2Table = (tableName as text) as table =>
        let
            Content = Binary.Buffer(
                Web.Contents(
                    R2BaseUrl,
                    [RelativePath = AnalystPrefix & tableName & ".csv"]
                )
            ),
            Csv = Csv.Document(
                Content,
                [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
            ),
            Result = Table.PromoteHeaders(Csv, [PromoteAllScalars = true])
        in
            Result,
    Tables = [
        dim_district = LoadR2Table("dim_district"),
        dim_date = LoadR2Table("dim_date"),
        dim_hour = LoadR2Table("dim_hour"),
        fact_weather_daily = LoadR2Table("fact_weather_daily"),
        fact_weather_hourly = LoadR2Table("fact_weather_hourly"),
        fact_aqi_hourly = LoadR2Table("fact_aqi_hourly")
    ]
in
    Tables
