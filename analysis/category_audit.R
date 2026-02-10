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

# 1. Overall counts by category_type
cat("=== CATEGORY_TYPE COUNTS (all measures) ===\n")
df %>%
  count(category_type, sort = TRUE) %>%
  mutate(pct = round(n / sum(n) * 100, 1)) %>%
  print(n = 30)

# 2. How many counties have data for each type?
cat("\n=== COUNTIES WITH DATA PER TYPE ===\n")
df %>%
  group_by(category_type) %>%
  summarize(
    n_measures = n(),
    n_counties = n_distinct(county),
    pass_rate = round(mean(passed) * 100, 1),
    .groups = "drop"
  ) %>%
  arrange(desc(n_measures)) %>%
  print(n = 30)

# 3. The sparse ones - what do they look like?
cat("\n=== CATEGORY TYPES WITH < 50 MEASURES ===\n")
sparse <- df %>%
  group_by(category_type) %>%
  summarize(
    n = n(),
    n_counties = n_distinct(county),
    counties = paste(sort(unique(county))[1:min(5, n_distinct(county))], collapse = ", "),
    pass_rate = round(mean(passed) * 100, 1),
    .groups = "drop"
  ) %>%
  filter(n < 50) %>%
  arrange(n)

sparse %>% print(n = 20, width = 150)

# 4. What does the matrix actually look like? Top 20 counties x all types
cat("\n=== MATRIX SPARSITY: top 20 counties x category_type ===\n")
top20 <- df %>% count(county, sort = TRUE) %>% head(20) %>% pull(county)

matrix_data <- df %>%
  filter(county %in% top20) %>%
  count(county, category_type) %>%
  pivot_wider(names_from = category_type, values_from = n, values_fill = 0)

matrix_data %>% print(n = 20, width = 300)

# 5. What are Gann Limit measures?
cat("\n=== GANN LIMIT SAMPLE ===\n")
df %>%
  filter(category_type == "Gann Limit") %>%
  select(year, county, measure_letter, title, percent_yes, passed) %>%
  head(10) %>%
  print(width = 200)

# 6. What are Revenue Bond measures?
cat("\n=== REVENUE BOND SAMPLE ===\n")
df %>%
  filter(category_type == "Revenue Bond") %>%
  select(year, county, measure_letter, title, percent_yes, passed) %>%
  head(10) %>%
  print(width = 200)

# 7. Development Tax sample
cat("\n=== DEVELOPMENT TAX SAMPLE ===\n")
df %>%
  filter(category_type == "Development Tax") %>%
  select(year, county, measure_letter, title, percent_yes, passed) %>%
  head(10) %>%
  print(width = 200)

# 8. Gasoline Tax sample
cat("\n=== GASOLINE TAX SAMPLE ===\n")
df %>%
  filter(category_type == "Gasoline Tax") %>%
  select(year, county, measure_letter, title, percent_yes, passed) %>%
  print(width = 200)

# 9. Policy/Position sample
cat("\n=== POLICY/POSITION SAMPLE ===\n")
df %>%
  filter(category_type == "Policy/Position") %>%
  select(year, county, measure_letter, title, percent_yes, passed) %>%
  head(10) %>%
  print(width = 200)

# 10. Advisory sample
cat("\n=== ADVISORY SAMPLE ===\n")
df %>%
  filter(category_type == "Advisory") %>%
  select(year, county, measure_letter, title, percent_yes, passed) %>%
  head(10) %>%
  print(width = 200)

cat("\nDone!\n")
