library(tidyverse)

df <- read_csv(
  "C:/Users/igorg/OneDrive/Desktop/personal/projects/cal_vgp/scraper/data/processed/ceda_parsed.csv",
  show_col_types = FALSE
) %>%
  filter(
    is_active == TRUE, is_duplicate == FALSE,
    !is.na(percent_yes), percent_yes > 0, !is.na(passed)
  ) %>%
  mutate(passed = as.numeric(passed), percent_yes = as.numeric(percent_yes), year = as.integer(year))

# SF sales tax measures - every single one
cat("=== ALL SAN FRANCISCO SALES TAX MEASURES ===\n")
df %>%
  filter(toupper(county) == "SAN FRANCISCO", category_type == "Sales Tax") %>%
  select(year, measure_letter, title, percent_yes, passed) %>%
  arrange(year) %>%
  print(n = 20, width = 120)

# Kern sales tax measures - every single one
cat("\n=== ALL KERN COUNTY SALES TAX MEASURES ===\n")
df %>%
  filter(toupper(county) == "KERN", category_type == "Sales Tax") %>%
  select(year, measure_letter, title, percent_yes, passed) %>%
  arrange(year) %>%
  print(n = 30, width = 120)

# How about ALL tax types combined for SF vs Kern?
cat("\n=== SF vs KERN: ALL TAX TYPES ===\n")
df %>%
  filter(toupper(county) %in% c("SAN FRANCISCO", "KERN"),
         category_type %in% c("Sales Tax", "Property Tax", "Business Tax",
                              "Utility Tax", "Miscellaneous Tax", "Transient Occupancy Tax")) %>%
  group_by(county = toupper(county), category_type) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  pivot_wider(names_from = county, values_from = c(n, pass_rate)) %>%
  print(width = 120)

# SF vs Kern over time (all fiscal measures)
cat("\n=== SF vs KERN FISCAL MEASURES BY DECADE ===\n")
df %>%
  filter(toupper(county) %in% c("SAN FRANCISCO", "KERN"),
         category_type %in% c("Sales Tax", "Property Tax", "Business Tax",
                              "Utility Tax", "Miscellaneous Tax", "Transient Occupancy Tax",
                              "GO Bond")) %>%
  mutate(era = ifelse(year <= 2010, "1998-2010", "2012-2024")) %>%
  group_by(county = toupper(county), era) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  pivot_wider(names_from = county, values_from = c(n, pass_rate)) %>%
  print(width = 120)

cat("\nDone!\n")
