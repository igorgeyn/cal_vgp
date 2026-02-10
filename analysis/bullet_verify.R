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

# Verify LA property tax
cat("=== LA COUNTY PROPERTY TAX ===\n")
df %>%
  filter(toupper(county) == "LOS ANGELES", category_type == "Property Tax") %>%
  select(year, measure_letter, title, percent_yes, passed) %>%
  arrange(year) %>%
  print(n = 20, width = 200)

# OC sales tax detail
cat("\n=== ORANGE COUNTY SALES TAX DETAILS ===\n")
df %>%
  filter(toupper(county) == "ORANGE", category_type == "Sales Tax") %>%
  select(year, measure_letter, title, percent_yes, passed) %>%
  arrange(year) %>%
  print(n = 25, width = 200)

# Tulare cannabis detail
cat("\n=== TULARE COUNTY CANNABIS MEASURES ===\n")
df %>%
  filter(toupper(county) == "TULARE",
         str_detect(tolower(paste(title, ballot_question, description, sep = " ")), "marijuana|cannabis")) %>%
  select(year, measure_letter, title, percent_yes, passed) %>%
  print(n = 10, width = 200)

# Merced vs SF overall
cat("\n=== MERCED vs SF ===\n")
df %>%
  filter(toupper(county) %in% c("MERCED", "SAN FRANCISCO")) %>%
  group_by(county = toupper(county)) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1), .groups = "drop") %>%
  print()

# Statewide recall detail
cat("\n=== RECALL DETAIL: successes and failures ===\n")
df %>%
  filter(category_type == "Recall") %>%
  summarize(
    total = n(),
    succeeded = sum(passed == 1),
    failed = sum(passed == 0),
    success_rate = round(mean(passed) * 100, 1)
  ) %>%
  print()

# San Bernardino education premium detail
cat("\n=== SAN BERNARDINO EDUCATION PREMIUM ===\n")
df %>%
  filter(toupper(county) == "SAN BERNARDINO",
         category_type %in% c("GO Bond", "Parcel Tax", "Sales Tax", "Property Tax")) %>%
  mutate(is_ed = str_detect(tolower(paste(title, ballot_question, description, sep=" ")),
                            "school|education|college|university|student|classroom")) %>%
  group_by(is_ed) %>%
  summarize(n = n(), pass_rate = round(mean(passed) * 100, 1),
            avg_yes = round(mean(percent_yes), 1), .groups = "drop") %>%
  print()

cat("\nEducation measures:\n")
df %>%
  filter(toupper(county) == "SAN BERNARDINO",
         category_type %in% c("GO Bond", "Parcel Tax", "Sales Tax", "Property Tax"),
         str_detect(tolower(paste(title, ballot_question, description, sep=" ")),
                    "school|education|college|university|student|classroom")) %>%
  select(year, measure_letter, category_type, title, percent_yes, passed) %>%
  print(n = 15, width = 200)

cat("\nDone!\n")
