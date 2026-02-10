library(tidyverse)

df <- read_csv(
  "C:/Users/igorg/OneDrive/Desktop/personal/projects/cal_vgp/scraper/data/processed/ceda_parsed.csv",
  show_col_types = FALSE
) %>%
  filter(
    is_active == TRUE, is_duplicate == FALSE,
    !is.na(percent_yes), percent_yes > 0, !is.na(passed)
  ) %>%
  mutate(
    passed      = as.numeric(passed),
    percent_yes = as.numeric(percent_yes),
    year        = as.integer(year)
  )

cat(sprintf("Total: %d measures\n\n", nrow(df)))

# 1. County x category_type pass rates (n>=5)
cat("=== COUNTY x MEASURE TYPE PASS RATES (n>=5) ===\n")
ct <- df %>%
  group_by(county, category_type) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  filter(n >= 5)
ct %>% arrange(category_type, pass_rate) %>% print(n = 300)

# 2. Perfect records: counties that ALWAYS pass or ALWAYS fail a type (n>=5)
cat("\n\n=== PERFECT RECORDS (100% or 0% pass rate, n>=5) ===\n")
ct %>% filter(pass_rate == 100 | pass_rate == 0) %>%
  arrange(pass_rate, desc(n)) %>% print(n = 100)

# 3. Counties that have NEVER passed a specific type (n>=3)
cat("\n\n=== NEVER PASSED (0% rate, n>=3) ===\n")
df %>%
  group_by(county, category_type) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  filter(n >= 3, pass_rate == 0) %>%
  arrange(desc(n)) %>% print(n = 50)

# 4. Surprising liberal-conservative pairs with similar rates
cat("\n\n=== GO BOND PASS RATES BY COUNTY (n>=5) ===\n")
ct %>% filter(category_type == "GO Bond") %>% arrange(desc(pass_rate)) %>% print(n = 30)

cat("\n\n=== SALES TAX PASS RATES BY COUNTY (n>=5) ===\n")
ct %>% filter(category_type == "Sales Tax") %>% arrange(desc(pass_rate)) %>% print(n = 30)

cat("\n\n=== PROPERTY TAX PASS RATES BY COUNTY (n>=3) ===\n")
df %>%
  filter(category_type == "Property Tax") %>%
  group_by(county) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1),
            avg_yes = round(mean(percent_yes), 1), .groups = "drop") %>%
  filter(n >= 3) %>% arrange(desc(pass_rate)) %>% print(n = 30)

# 5. Measures with exactly 50% (razor thin)
cat("\n\n=== MEASURES WITHIN 0.5pp OF 50% ===\n")
df %>%
  filter(abs(percent_yes - 50) < 0.5) %>%
  select(year, county, measure_letter, category_type, percent_yes, passed) %>%
  arrange(abs(percent_yes - 50)) %>% print(n = 20)

# 6. Measures that got 100% YES
cat("\n\n=== MEASURES WITH 100% YES ===\n")
df %>%
  filter(percent_yes >= 99) %>%
  select(year, county, measure_letter, category_type, percent_yes) %>%
  arrange(desc(percent_yes)) %>% print(n = 20)

# 7. Topic/keyword search for interesting subjects
cat("\n\n=== MEASURES MENTIONING 'HOMELESS' ===\n")
df %>%
  filter(str_detect(tolower(paste(title, ballot_question, description, sep = " ")), "homeless")) %>%
  select(year, county, measure_letter, category_type, percent_yes, passed) %>%
  print(n = 30)

cat("\n\n=== MEASURES MENTIONING 'MARIJUANA' OR 'CANNABIS' ===\n")
df %>%
  filter(str_detect(tolower(paste(title, ballot_question, description, sep = " ")), "marijuana|cannabis")) %>%
  group_by(county) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  arrange(desc(n)) %>% print(n = 30)

cat("\n\n=== PARCEL TAX PASS RATES BY COUNTY (n>=3) ===\n")
df %>%
  filter(category_type == "Parcel Tax") %>%
  group_by(county) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1),
            avg_yes = round(mean(percent_yes), 1), .groups = "drop") %>%
  filter(n >= 3) %>% arrange(pass_rate) %>% print(n = 30)

# 8. Overall pass rate by category_type
cat("\n\n=== OVERALL PASS RATE BY MEASURE TYPE ===\n")
df %>%
  group_by(category_type) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  arrange(desc(n)) %>% print(n = 30)

# 9. Statewide (Prop) vs local comparison
cat("\n\n=== STATEWIDE vs LOCAL ===\n")
df %>%
  mutate(level = ifelse(county == "Statewide", "Statewide", "Local")) %>%
  group_by(level) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  print()

# 10. Biggest single-county outliers vs statewide avg for a type
cat("\n\n=== RECALL PASS RATES BY COUNTY (n>=3) ===\n")
df %>%
  filter(category_type == "Recall") %>%
  group_by(county) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  filter(n >= 3) %>% arrange(pass_rate) %>% print(n = 30)

# 11. How many measures per county?
cat("\n\n=== MEASURES PER COUNTY (top and bottom) ===\n")
df %>%
  group_by(county) %>%
  summarize(n = n(), .groups = "drop") %>%
  arrange(desc(n)) %>% print(n = 10)
cat("...\n")
df %>%
  group_by(county) %>%
  summarize(n = n(), .groups = "drop") %>%
  arrange(n) %>% print(n = 10)

cat("\nDone!\n")
