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
    passed = as.numeric(passed),
    percent_yes = as.numeric(percent_yes),
    year = as.integer(year)
  )

# ============================================================
# 1. SUPERMAJORITY TRAP: measures that won majority but failed
# ============================================================
cat("=== SUPERMAJORITY TRAP ===\n")
trap <- df %>% filter(passed == 0, percent_yes >= 50)
cat(sprintf("Total measures that got majority YES but FAILED: %d\n", nrow(trap)))
trap %>%
  filter(percent_yes >= 55) %>%
  select(year, county, measure_letter, category_type, percent_yes, passed) %>%
  arrange(desc(percent_yes)) %>%
  print(n = 30)

cat(sprintf("\nMeasures with 60%%+ YES that still failed: %d\n",
            sum(trap$percent_yes >= 60)))

# ============================================================
# 2. CONSERVATIVE COUNTIES PASSING LIBERAL MEASURES
# ============================================================
cat("\n=== CONSERVATIVE COUNTIES: CANNABIS MEASURES ===\n")
df %>%
  filter(str_detect(tolower(paste(title, ballot_question, description, sep = " ")), "marijuana|cannabis")) %>%
  group_by(county) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  filter(n >= 2) %>%
  arrange(desc(pass_rate)) %>%
  print(n = 30)

# ============================================================
# 3. ORANGE COUNTY specifics (famously conservative, now purple)
# ============================================================
cat("\n=== ORANGE COUNTY FISCAL MEASURES ===\n")
df %>%
  filter(toupper(county) == "ORANGE") %>%
  count(category_type, sort = TRUE) %>%
  print(n = 20)

cat("\nOC pass rates by type:\n")
df %>%
  filter(toupper(county) == "ORANGE") %>%
  group_by(category_type) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  filter(n >= 3) %>%
  arrange(desc(pass_rate)) %>%
  print(n = 20)

# ============================================================
# 4. EDUCATION vs NON-EDUCATION across red/blue counties
# ============================================================
cat("\n=== EDUCATION PREMIUM BY COUNTY (n>=10 each) ===\n")
ed_premium <- df %>%
  filter(category_type %in% c("GO Bond", "Parcel Tax", "Sales Tax", "Property Tax")) %>%
  mutate(is_ed = str_detect(tolower(paste(title, ballot_question, description, sep=" ")),
                            "school|education|college|university|student|classroom")) %>%
  group_by(county, is_ed) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  filter(n >= 5) %>%
  pivot_wider(names_from = is_ed, values_from = c(n, pass_rate),
              names_glue = "{.value}_{ifelse(is_ed, 'ed', 'noned')}") %>%
  filter(!is.na(pass_rate_ed), !is.na(pass_rate_noned)) %>%
  mutate(premium = pass_rate_ed - pass_rate_noned) %>%
  arrange(desc(premium))

ed_premium %>% print(n = 20)

# ============================================================
# 5. RECALL success rates (politically juicy)
# ============================================================
cat("\n=== RECALL MEASURES ===\n")
df %>%
  filter(category_type == "Recall") %>%
  group_by(county) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  arrange(desc(n)) %>%
  print(n = 20)

cat(sprintf("\nOverall recall success rate: %.1f%% (n=%d)\n",
            mean(df$passed[df$category_type == "Recall"]) * 100,
            sum(df$category_type == "Recall")))

# ============================================================
# 6. HOMELESSNESS measures
# ============================================================
cat("\n=== HOMELESSNESS MEASURES ===\n")
homeless <- df %>%
  filter(str_detect(tolower(paste(title, ballot_question, description, sep = " ")), "homeless"))
cat(sprintf("Total homelessness measures: %d\n", nrow(homeless)))
cat(sprintf("Pass rate: %.1f%%\n", mean(homeless$passed) * 100))

homeless %>%
  select(year, county, measure_letter, category_type, percent_yes, passed) %>%
  arrange(county, year) %>%
  print(n = 40)

# LA specifically
cat("\nLA homelessness:\n")
homeless %>%
  filter(toupper(county) == "LOS ANGELES") %>%
  select(year, measure_letter, title, percent_yes, passed) %>%
  print(n = 10, width = 200)

# ============================================================
# 7. PERFECT STREAKS: counties that always pass or always fail
# ============================================================
cat("\n=== PERFECT PASS STREAKS (100%, n>=5) ===\n")
df %>%
  group_by(county, category_type) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  filter(n >= 5, pass_rate == 100) %>%
  arrange(desc(n)) %>%
  print(n = 30)

cat("\n=== PERFECT FAIL STREAKS (0%, n>=5) ===\n")
df %>%
  group_by(county, category_type) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  filter(n >= 5, pass_rate == 0) %>%
  arrange(desc(n)) %>%
  print(n = 30)

# ============================================================
# 8. OVERALL PASS RATE comparison: surprising pairings
# ============================================================
cat("\n=== OVERALL PASS RATE BY COUNTY (n>=30) ===\n")
df %>%
  group_by(county) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  filter(n >= 30) %>%
  arrange(desc(pass_rate)) %>%
  print(n = 40)

# ============================================================
# 9. GO BONDS specifically (require 55% or 2/3)
# ============================================================
cat("\n=== GO BOND PASS RATES (n>=3) ===\n")
df %>%
  filter(category_type == "GO Bond") %>%
  group_by(county) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1),
            avg_yes = round(mean(percent_yes), 1), .groups = "drop") %>%
  filter(n >= 3) %>%
  arrange(pass_rate) %>%
  print(n = 30)

# ============================================================
# 10. PARCEL TAX - notoriously hard to pass (needs 2/3)
# ============================================================
cat("\n=== PARCEL TAX PASS RATES (n>=3) ===\n")
df %>%
  filter(category_type == "Parcel Tax") %>%
  group_by(county) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1),
            avg_yes = round(mean(percent_yes), 1), .groups = "drop") %>%
  filter(n >= 3) %>%
  arrange(desc(pass_rate)) %>%
  print(n = 30)

# Overall parcel tax pass rate
cat(sprintf("\nOverall parcel tax pass rate: %.1f%% (n=%d)\n",
            mean(df$passed[df$category_type == "Parcel Tax"]) * 100,
            sum(df$category_type == "Parcel Tax")))

# ============================================================
# 11. UTILITY TAX - who keeps passing these?
# ============================================================
cat("\n=== UTILITY TAX (n>=5) ===\n")
df %>%
  filter(category_type == "Utility Tax") %>%
  group_by(county) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  filter(n >= 5) %>%
  arrange(pass_rate) %>%
  print(n = 20)

# ============================================================
# 12. HIGHEST YES% measures ever
# ============================================================
cat("\n=== HIGHEST YES% MEASURES (>90%) ===\n")
df %>%
  filter(percent_yes >= 90) %>%
  select(year, county, measure_letter, category_type, title, percent_yes) %>%
  arrange(desc(percent_yes)) %>%
  print(n = 20, width = 200)

# ============================================================
# 13. STATEWIDE average pass rates over time
# ============================================================
cat("\n=== STATEWIDE PASS RATE BY YEAR ===\n")
df %>%
  group_by(year) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  print(n = 30)

# ============================================================
# 14. Sales tax specifically across political spectrum
# ============================================================
cat("\n=== SALES TAX PASS RATES (n>=5) ===\n")
df %>%
  filter(category_type == "Sales Tax") %>%
  group_by(county) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  filter(n >= 5) %>%
  arrange(desc(pass_rate)) %>%
  print(n = 30)

# ============================================================
# 15. TRANSIENT OCCUPANCY TAX (hotel tax)
# ============================================================
cat("\n=== TRANSIENT OCCUPANCY TAX (n>=5) ===\n")
df %>%
  filter(category_type == "Transient Occupancy Tax") %>%
  group_by(county) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  filter(n >= 5) %>%
  arrange(pass_rate) %>%
  print(n = 20)

cat(sprintf("\nOverall TOT pass rate: %.1f%% (n=%d)\n",
            mean(df$passed[df$category_type == "Transient Occupancy Tax"]) * 100,
            sum(df$category_type == "Transient Occupancy Tax")))

# ============================================================
# 16. Counties where NOTHING passes
# ============================================================
cat("\n=== LOWEST OVERALL PASS RATE COUNTIES (n>=20) ===\n")
df %>%
  group_by(county) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  filter(n >= 20) %>%
  arrange(pass_rate) %>%
  print(n = 15)

# ============================================================
# 17. Time shift: 2020+ vs pre-2020
# ============================================================
cat("\n=== POST-COVID SHIFT: 2020-2024 vs 2014-2018 ===\n")
df %>%
  filter(year >= 2014) %>%
  mutate(era = ifelse(year >= 2020, "2020-2024", "2014-2018")) %>%
  group_by(era) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  print()

cat("\nBy type:\n")
df %>%
  filter(year >= 2014,
         category_type %in% c("Sales Tax", "GO Bond", "Parcel Tax", "Property Tax")) %>%
  mutate(era = ifelse(year >= 2020, "2020-2024", "2014-2018")) %>%
  group_by(era, category_type) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  pivot_wider(names_from = era, values_from = c(n, pass_rate)) %>%
  print(width = 120)

cat("\nDone!\n")
