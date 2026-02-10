library(tidyverse)

df <- read_csv(
  "C:/Users/igorg/OneDrive/Desktop/personal/projects/cal_vgp/scraper/data/processed/ceda_parsed.csv",
  show_col_types = FALSE
) %>%
  filter(
    is_active == TRUE, is_duplicate == FALSE,
    !is.na(percent_yes), percent_yes > 0, !is.na(passed)
  )

sf <- df %>% filter(toupper(county) == "SAN FRANCISCO")

cat("=== SF MEASURES BY TYPE ===\n")
sf %>% count(category_type, sort = TRUE) %>% print(n = 30)

cat("\n=== SF SALES TAX DETAILS ===\n")
sf %>%
  filter(category_type == "Sales Tax") %>%
  select(year, measure_letter, title, percent_yes, passed) %>%
  print(n = 10, width = 200)

cat("\n=== SF BUSINESS TAX DETAILS ===\n")
sf %>%
  filter(category_type == "Business Tax") %>%
  select(year, measure_letter, title, percent_yes, passed) %>%
  print(n = 20, width = 200)

cat("\n=== SF MISCELLANEOUS TAX DETAILS ===\n")
sf %>%
  filter(category_type == "Miscellaneous Tax") %>%
  select(year, measure_letter, title, percent_yes, passed) %>%
  print(n = 20, width = 200)

# Compare: how do big urban counties distribute their fiscal measures?
cat("\n=== FISCAL MEASURE TYPE DISTRIBUTION: BIG URBAN COUNTIES ===\n")
df %>%
  filter(toupper(county) %in% c("SAN FRANCISCO", "LOS ANGELES", "ALAMEDA",
                                  "SANTA CLARA", "SAN DIEGO", "SACRAMENTO")) %>%
  filter(category_type %in% c("Sales Tax", "Property Tax", "Business Tax",
                               "Utility Tax", "Miscellaneous Tax", "Parcel Tax",
                               "GO Bond", "Transient Occupancy Tax")) %>%
  count(county, category_type) %>%
  pivot_wider(names_from = category_type, values_from = n, values_fill = 0) %>%
  print(width = 200)

cat("\nDone!\n")
