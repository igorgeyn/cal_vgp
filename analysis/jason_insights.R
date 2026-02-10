###############################################################################
# California Ballot Measures: Patterns, Trends & Curiosities
# ---------------------------------------------------------
# An exploratory analysis of ~11K county-level ballot measures (1998-2024)
# from the California Elections Data Archive (CEDA).
#
# Designed for someone who:
#   - Lives in California
#   - Has a college degree and follows local politics
#   - Wonders whether certain counties are "locked in" on certain issues
#
# Special investigation: "LA County never votes against a property tax increase"
###############################################################################

# --- 0. Setup ----------------------------------------------------------------

library(tidyverse)   # dplyr, ggplot2, tidyr, readr, stringr, forcats, etc.
library(scales)      # label_percent, label_comma
library(patchwork)   # composing multi-panel figures

theme_set(
  theme_minimal(base_size = 13) +
    theme(
      plot.title    = element_text(face = "bold", size = 14),
      plot.subtitle = element_text(color = "grey40"),
      strip.text    = element_text(face = "bold"),
      legend.position = "bottom"
    )
)

ca_blue  <- "#003DA5"
ca_gold  <- "#FDB515"
ca_red   <- "#C4122F"
ca_green <- "#2D8C3C"

# --- 1. Load & clean ---------------------------------------------------------

project_root <- "C:/Users/igorg/OneDrive/Desktop/personal/projects/cal_vgp"
fig_dir      <- file.path(project_root, "analysis")

raw <- read_csv(
  file.path(project_root, "scraper", "data", "processed", "ceda_parsed.csv"),
  show_col_types = FALSE
)

df <- raw %>%
  filter(
    is_active == TRUE,
    is_duplicate == FALSE,
    !is.na(percent_yes),        # need vote data
    percent_yes > 0,            # drop zero-vote placeholders
    !is.na(passed)
  ) %>%
  mutate(
    passed      = as.numeric(passed),
    percent_yes = as.numeric(percent_yes),
    year        = as.integer(year),
    county      = str_to_title(county),   # "LOS ANGELES" -> "Los Angeles"
    # Broad topic buckets for readability
    topic = case_when(
      str_detect(category_type, regex("property tax", ignore_case = TRUE))
        ~ "Property Tax",
      str_detect(category_type, regex("sales tax", ignore_case = TRUE))
        ~ "Sales Tax",
      str_detect(category_type, regex("GO bond|general obligation", ignore_case = TRUE))
        ~ "GO Bond",
      str_detect(category_type, regex("charter", ignore_case = TRUE))
        ~ "Charter Amendment",
      str_detect(category_type, regex("ordinance", ignore_case = TRUE))
        ~ "Ordinance",
      str_detect(category_type, regex("parcel tax", ignore_case = TRUE))
        ~ "Parcel Tax",
      str_detect(category_type, regex("utility|user", ignore_case = TRUE))
        ~ "Utility/User Tax",
      str_detect(category_type, regex("transient|hotel|TOT", ignore_case = TRUE))
        ~ "Hotel/TOT Tax",
      str_detect(category_type, regex("special tax", ignore_case = TRUE))
        ~ "Special Tax",
      str_detect(category_type, regex("recall", ignore_case = TRUE))
        ~ "Recall",
      str_detect(category_type, regex("advisory", ignore_case = TRUE))
        ~ "Advisory",
      TRUE ~ "Other"
    ),
    is_tax_or_bond = topic %in% c(
      "Property Tax", "Sales Tax", "GO Bond",
      "Parcel Tax", "Special Tax", "Utility/User Tax", "Hotel/TOT Tax"
    ),
    # CA regions (simplified)
    region = case_when(
      county %in% c("San Francisco", "San Mateo", "Santa Clara", "Alameda",
                     "Contra Costa", "Marin", "Sonoma", "Napa", "Solano")
        ~ "Bay Area",
      county %in% c("Los Angeles")
        ~ "Los Angeles",
      county %in% c("Orange", "San Diego", "Ventura",
                     "Santa Barbara", "San Luis Obispo")
        ~ "Southern Coast",
      county %in% c("Riverside", "San Bernardino", "Imperial")
        ~ "Inland Empire",
      county %in% c("Sacramento", "Placer", "El Dorado", "Yolo")
        ~ "Sacramento Metro",
      county %in% c("Fresno", "Kern", "Tulare", "Kings", "Madera",
                     "Merced", "Stanislaus", "San Joaquin")
        ~ "Central Valley",
      county %in% c("Humboldt", "Mendocino", "Del Norte", "Lake",
                     "Trinity", "Shasta", "Siskiyou", "Tehama",
                     "Lassen", "Modoc", "Plumas", "Glenn", "Butte",
                     "Colusa")
        ~ "North State / Rural",
      TRUE ~ "Other CA"
    )
  )

cat(sprintf(
  "\nLoaded %s measures across %s counties, %s-%s\n\n",
  comma(nrow(df)), n_distinct(df$county), min(df$year), max(df$year)
))


###############################################################################
# ANALYSIS 1 — "LA County never votes against a property tax increase"
###############################################################################

cat("=" |> strrep(72), "\n")
cat("ANALYSIS 1: Does LA County ever vote down a property tax increase?\n")
cat("=" |> strrep(72), "\n\n")

la_prop_tax <- df %>%
  filter(county == "Los Angeles", topic == "Property Tax") %>%
  arrange(year) %>%
  select(year, election_date, measure_letter, title, percent_yes, passed)

cat(sprintf(
  "LA County property tax measures: %d total, %d passed, %d failed\n",
  nrow(la_prop_tax),
  sum(la_prop_tax$passed == 1),
  sum(la_prop_tax$passed == 0)
))

cat("\nAll LA County property tax measures:\n")
la_prop_tax %>%
  mutate(
    result  = if_else(passed == 1, "PASS", "FAIL"),
    pct_yes = sprintf("%.1f%%", percent_yes)
  ) %>%
  select(year, measure_letter, pct_yes, result) %>%
  print(n = Inf)

# Compare LA to all other counties
prop_tax_by_county <- df %>%
  filter(topic == "Property Tax") %>%
  group_by(county) %>%
  summarize(
    n_measures = n(),
    n_passed   = sum(passed == 1),
    pass_rate  = mean(passed),
    avg_yes    = mean(percent_yes),
    .groups    = "drop"
  ) %>%
  filter(n_measures >= 5) %>%
  arrange(desc(pass_rate))

cat("\nProperty Tax pass rates (counties with 5+ measures):\n")
cat("Top 10 most favorable:\n")
prop_tax_by_county %>% slice_head(n = 10) %>% print()
cat("\nBottom 10 least favorable:\n")
prop_tax_by_county %>% slice_tail(n = 10) %>% print()

# --- Figure 1: LA vs. Rest on property taxes --------------------------------

p1 <- df %>%
  filter(topic == "Property Tax") %>%
  mutate(is_la = if_else(county == "Los Angeles", "Los Angeles", "All Other Counties")) %>%
  ggplot(aes(x = percent_yes, fill = is_la)) +
  geom_density(alpha = 0.5, color = NA) +
  geom_vline(xintercept = 66.67, linetype = "dashed", color = "grey30") +
  annotate("text", x = 68, y = Inf, vjust = 2, hjust = 0, size = 3.2,
           label = "2/3 supermajority\nthreshold", color = "grey30") +
  scale_fill_manual(values = c("Los Angeles" = ca_blue, "All Other Counties" = "grey70")) +
  labs(
    title    = "Jason's Dad Might Be Right",
    subtitle = "Distribution of YES% on property tax measures, 1998-2024",
    x = "Percent YES", y = "Density", fill = NULL
  ) +
  scale_x_continuous(labels = label_percent(scale = 1))

ggsave(file.path(fig_dir, "fig1_la_property_tax.png"), p1, width = 8, height = 5, dpi = 200)


###############################################################################
# ANALYSIS 2 — "Immovable" counties: who NEVER changes their mind?
###############################################################################

cat("\n\n", "=" |> strrep(72), "\n")
cat("ANALYSIS 2: Which counties are most consistent by topic?\n")
cat("=" |> strrep(72), "\n\n")

# For each county × topic combo with ≥5 measures, how consistent is the vote?
consistency <- df %>%
  group_by(county, topic) %>%
  summarize(
    n         = n(),
    pass_rate = mean(passed),
    avg_yes   = mean(percent_yes),
    min_yes   = min(percent_yes),
    max_yes   = max(percent_yes),
    years     = paste(range(year), collapse = "-"),
    .groups   = "drop"
  ) %>%
  filter(n >= 5) %>%
  mutate(
    # "Consistency" = how close to 0% or 100% pass rate
    consistency = pmax(pass_rate, 1 - pass_rate)
  )

# Perfect records: 100% pass or 100% fail on a topic
perfect <- consistency %>%
  filter(pass_rate == 1 | pass_rate == 0) %>%
  arrange(desc(n))

cat("Counties with PERFECT pass or fail records on a topic (≥5 measures):\n")
perfect %>%
  mutate(verdict = if_else(pass_rate == 1, "Always passes", "Always fails")) %>%
  select(county, topic, n, verdict, avg_yes, years) %>%
  print(n = 30)

# --- Figure 2: Heatmap of pass rates by county (top counties) × topic -------

top_counties <- df %>%
  count(county, sort = TRUE) %>%
  slice_head(n = 20) %>%
  pull(county)

main_topics <- c("GO Bond", "Property Tax", "Sales Tax", "Ordinance",
                 "Charter Amendment", "Parcel Tax")

p2 <- df %>%
  filter(county %in% top_counties, topic %in% main_topics) %>%
  group_by(county, topic) %>%
  summarize(
    pass_rate = mean(passed),
    n         = n(),
    .groups   = "drop"
  ) %>%
  filter(n >= 3) %>%
  mutate(county = fct_reorder(county, pass_rate, .fun = mean)) %>%
  ggplot(aes(x = topic, y = county, fill = pass_rate)) +
  geom_tile(color = "white", linewidth = 0.5) +
  geom_text(aes(label = sprintf("%d%%\n(n=%d)", round(pass_rate * 100), n)),
            size = 2.8, color = "white") +
  scale_fill_gradient2(
    low = ca_red, mid = "grey85", high = ca_blue, midpoint = 0.5,
    labels = label_percent()
  ) +
  labs(
    title    = "How the 20 Biggest Counties Vote, by Measure Type",
    subtitle = "Pass rate on ballot measures, 1998-2024 (minimum 3 measures)",
    x = NULL, y = NULL, fill = "Pass rate"
  ) +
  theme(axis.text.x = element_text(angle = 30, hjust = 1))

ggsave(file.path(fig_dir, "fig2_county_topic_heatmap.png"), p2, width = 10, height = 8, dpi = 200)


###############################################################################
# ANALYSIS 3 — Has California become more or less friendly to taxes over time?
###############################################################################

cat("\n\n", "=" |> strrep(72), "\n")
cat("ANALYSIS 3: Tax/bond friendliness over time\n")
cat("=" |> strrep(72), "\n\n")

tax_trend <- df %>%
  filter(is_tax_or_bond, year %% 2 == 0) %>%  # even years (larger samples)
  group_by(year, topic) %>%
  summarize(
    n_measures = n(),
    pass_rate  = mean(passed),
    avg_yes    = mean(percent_yes),
    .groups    = "drop"
  )

cat("Statewide tax/bond pass rates by year:\n")
tax_trend %>%
  group_by(year) %>%
  summarize(
    total   = sum(n_measures),
    overall = weighted.mean(pass_rate, n_measures),
    .groups = "drop"
  ) %>%
  mutate(overall = sprintf("%.1f%%", overall * 100)) %>%
  print(n = Inf)

p3 <- tax_trend %>%
  filter(topic %in% c("GO Bond", "Property Tax", "Sales Tax", "Parcel Tax")) %>%
  ggplot(aes(x = year, y = pass_rate, color = topic)) +
  geom_line(linewidth = 1) +
  geom_point(aes(size = n_measures), alpha = 0.7) +
  scale_y_continuous(labels = label_percent(), limits = c(0, 1)) +
  scale_color_manual(values = c(
    "GO Bond"      = ca_blue,
    "Property Tax"  = ca_gold,
    "Sales Tax"     = ca_red,
    "Parcel Tax"    = ca_green
  )) +
  labs(
    title    = "Are Californians Getting More Open to Taxes?",
    subtitle = "Pass rate by fiscal measure type, even-year elections 1998-2024",
    x = NULL, y = "Pass rate", color = "Measure type", size = "# measures"
  )

ggsave(file.path(fig_dir, "fig3_tax_trend.png"), p3, width = 9, height = 5.5, dpi = 200)


###############################################################################
# ANALYSIS 4 — Regional personality: Bay Area vs. Inland Empire vs. …
###############################################################################

cat("\n\n", "=" |> strrep(72), "\n")
cat("ANALYSIS 4: Regional voting personalities\n")
cat("=" |> strrep(72), "\n\n")

regional <- df %>%
  group_by(region, topic) %>%
  summarize(
    n         = n(),
    pass_rate = mean(passed),
    avg_yes   = mean(percent_yes),
    .groups   = "drop"
  ) %>%
  filter(n >= 10)

# Overall pass rate by region
regional_overall <- df %>%
  group_by(region) %>%
  summarize(
    n_measures = n(),
    pass_rate  = mean(passed),
    avg_yes    = mean(percent_yes),
    .groups    = "drop"
  ) %>%
  arrange(desc(pass_rate))

cat("Overall pass rate by region:\n")
regional_overall %>%
  mutate(pass_rate = sprintf("%.1f%%", pass_rate * 100),
         avg_yes   = sprintf("%.1f%%", avg_yes)) %>%
  print()

p4 <- regional %>%
  filter(topic %in% c("GO Bond", "Property Tax", "Sales Tax", "Ordinance")) %>%
  mutate(region = fct_reorder(region, pass_rate, .fun = mean)) %>%
  ggplot(aes(x = region, y = pass_rate, fill = topic)) +
  geom_col(position = position_dodge(width = 0.8), width = 0.7) +
  scale_y_continuous(labels = label_percent()) +
  scale_fill_manual(values = c(
    "GO Bond"       = ca_blue,
    "Property Tax"  = ca_gold,
    "Sales Tax"     = ca_red,
    "Ordinance"     = ca_green
  )) +
  coord_flip() +
  labs(
    title    = "California's Regional Voting Personalities",
    subtitle = "Pass rate on major measure types by region, 1998-2024",
    x = NULL, y = "Pass rate", fill = NULL
  )

ggsave(file.path(fig_dir, "fig4_regional_personality.png"), p4, width = 9, height = 6, dpi = 200)


###############################################################################
# ANALYSIS 5 — The tightest races and biggest blowouts
###############################################################################

cat("\n\n", "=" |> strrep(72), "\n")
cat("ANALYSIS 5: Closest calls and biggest blowouts\n")
cat("=" |> strrep(72), "\n\n")

cat("10 tightest races (closest to 50%):\n")
df %>%
  mutate(margin = abs(percent_yes - 50)) %>%
  arrange(margin) %>%
  select(year, county, measure_letter, topic, percent_yes, passed) %>%
  slice_head(n = 10) %>%
  print()

cat("\n10 most lopsided passes (highest YES%):\n")
df %>%
  filter(passed == 1) %>%
  arrange(desc(percent_yes)) %>%
  select(year, county, measure_letter, topic, percent_yes) %>%
  slice_head(n = 10) %>%
  print()

cat("\n10 most resounding defeats (lowest YES%):\n")
df %>%
  filter(passed == 0) %>%
  arrange(percent_yes) %>%
  select(year, county, measure_letter, topic, percent_yes) %>%
  slice_head(n = 10) %>%
  print()


###############################################################################
# ANALYSIS 6 — The "Education Premium": do school bonds get special treatment?
###############################################################################

cat("\n\n", "=" |> strrep(72), "\n")
cat("ANALYSIS 6: The education premium\n")
cat("=" |> strrep(72), "\n\n")

education_flag <- df %>%
  mutate(
    is_education = str_detect(
      paste(coalesce(title, ""), coalesce(category_topic, "")),
      regex("school|education|student|classroom|teacher|college|university|library",
            ignore_case = TRUE)
    )
  )

ed_comparison <- education_flag %>%
  filter(is_tax_or_bond) %>%
  group_by(is_education) %>%
  summarize(
    n         = n(),
    pass_rate = mean(passed),
    avg_yes   = mean(percent_yes),
    .groups   = "drop"
  )

cat("Tax/Bond measures: education-related vs. everything else:\n")
ed_comparison %>%
  mutate(
    label     = if_else(is_education, "Education-related", "Non-education"),
    pass_rate = sprintf("%.1f%%", pass_rate * 100),
    avg_yes   = sprintf("%.1f%%", avg_yes)
  ) %>%
  select(label, n, pass_rate, avg_yes) %>%
  print()

p5 <- education_flag %>%
  filter(is_tax_or_bond) %>%
  mutate(ed_label = if_else(is_education, "Education-related", "Non-education")) %>%
  ggplot(aes(x = percent_yes, fill = ed_label)) +
  geom_density(alpha = 0.5, color = NA) +
  geom_vline(xintercept = c(50, 66.67), linetype = "dashed", color = "grey40") +
  annotate("text", x = 51, y = Inf, vjust = 2, hjust = 0, size = 3,
           label = "Simple\nmajority", color = "grey40") +
  annotate("text", x = 68, y = Inf, vjust = 2, hjust = 0, size = 3,
           label = "2/3 super-\nmajority", color = "grey40") +
  scale_fill_manual(values = c("Education-related" = ca_blue, "Non-education" = "grey65")) +
  labs(
    title    = "The Education Premium",
    subtitle = "YES% distribution on tax/bond measures: education vs. everything else",
    x = "Percent YES", y = "Density", fill = NULL
  ) +
  scale_x_continuous(labels = label_percent(scale = 1))

ggsave(file.path(fig_dir, "fig5_education_premium.png"), p5, width = 8, height = 5, dpi = 200)


###############################################################################
# ANALYSIS 7 — Volatility: which counties swing the most election to election?
###############################################################################

cat("\n\n", "=" |> strrep(72), "\n")
cat("ANALYSIS 7: County volatility — who swings the most?\n")
cat("=" |> strrep(72), "\n\n")

volatility <- df %>%
  filter(is_tax_or_bond, year %% 2 == 0) %>%
  group_by(county, year) %>%
  summarize(avg_yes = mean(percent_yes), n = n(), .groups = "drop") %>%
  filter(n >= 3) %>%
  group_by(county) %>%
  filter(n() >= 4) %>%  # need ≥4 election cycles
  summarize(
    n_cycles      = n(),
    mean_yes      = mean(avg_yes),
    sd_yes        = sd(avg_yes),
    range_yes     = max(avg_yes) - min(avg_yes),
    .groups       = "drop"
  ) %>%
  arrange(desc(sd_yes))

cat("Most volatile counties (highest SD in avg YES% across election cycles):\n")
volatility %>% slice_head(n = 10) %>% print()

cat("\nMost stable counties (lowest SD):\n")
volatility %>% slice_tail(n = 10) %>% print()

# --- Figure 6: Spaghetti plot of top counties over time ---------------------

focus_counties <- c("Los Angeles", "San Francisco", "Orange", "San Diego",
                    "Fresno", "Sacramento", "Alameda", "Riverside")

p6 <- df %>%
  filter(is_tax_or_bond, county %in% focus_counties, year %% 2 == 0) %>%
  group_by(county, year) %>%
  summarize(avg_yes = mean(percent_yes), n = n(), .groups = "drop") %>%
  filter(n >= 2) %>%
  ggplot(aes(x = year, y = avg_yes, color = county)) +
  geom_line(linewidth = 0.9) +
  geom_point(size = 2) +
  geom_hline(yintercept = 66.67, linetype = "dashed", color = "grey50") +
  annotate("text", x = 1999, y = 68, hjust = 0, size = 3, color = "grey40",
           label = "2/3 threshold") +
  scale_y_continuous(labels = label_percent(scale = 1)) +
  labs(
    title    = "Tax Friendliness Over Time: 8 Key Counties",
    subtitle = "Average YES% on tax/bond measures per election cycle",
    x = NULL, y = "Avg. YES%", color = NULL
  )

ggsave(file.path(fig_dir, "fig6_county_timelines.png"), p6, width = 9, height = 5.5, dpi = 200)


###############################################################################
# ANALYSIS 8 — The Threshold Landscape: where do tax measures land?
###############################################################################

cat("\n\n", "=" |> strrep(72), "\n")
cat("ANALYSIS 8: The Threshold Landscape\n")
cat("=" |> strrep(72), "\n\n")

# California uses multiple approval thresholds depending on measure type:
#   - Simple majority (>50%): general taxes, ordinances, charters
#   - 55% (Prop 39, 2000): school facility bonds
#   - 2/3 supermajority (~66.7%): special taxes, some property taxes
#
# This creates a "no man's land" where a measure can win strong majority
# support but still fail. How many tax/bond measures land in this zone?

tax_threshold <- df %>%
  filter(is_tax_or_bond) %>%
  mutate(
    zone = case_when(
      percent_yes < 50                         ~ "Under 50%",
      percent_yes >= 50 & percent_yes < 55     ~ "50-55% (majority, not Prop 39)",
      percent_yes >= 55 & percent_yes < 66.67  ~ "55-66.7% (Prop 39 OK, not 2/3)",
      percent_yes >= 66.67                     ~ "Above 66.7% (clears all thresholds)"
    ),
    zone = factor(zone, levels = c(
      "Under 50%",
      "50-55% (majority, not Prop 39)",
      "55-66.7% (Prop 39 OK, not 2/3)",
      "Above 66.7% (clears all thresholds)"
    ))
  )

zone_summary <- tax_threshold %>%
  group_by(zone) %>%
  summarize(
    n         = n(),
    n_passed  = sum(passed == 1),
    n_failed  = sum(passed == 0),
    .groups   = "drop"
  ) %>%
  mutate(pct = sprintf("%.1f%%", 100 * n / sum(n)))

cat("Where do California tax/bond measures land?\n")
zone_summary %>% print()

# The "no man's land" measures — majority support but failed
no_mans_land <- tax_threshold %>%
  filter(passed == 0, percent_yes >= 50)

cat(sprintf(
  "\nTax/bond measures that won majority support but FAILED: %d\n",
  nrow(no_mans_land)
))
cat("These measures had majority YES votes but likely needed a supermajority:\n")
no_mans_land %>%
  arrange(desc(percent_yes)) %>%
  select(year, county, measure_letter, topic, percent_yes, passed) %>%
  print(n = 20)

# Broader view: how many measures live in the "danger zone" (50-66.7%)?
danger_zone <- tax_threshold %>%
  filter(percent_yes >= 50, percent_yes < 66.67)

cat(sprintf(
  "\n%d tax/bond measures (%.1f%%) landed in the 50-66.7%% zone.\n",
  nrow(danger_zone),
  100 * nrow(danger_zone) / nrow(tax_threshold)
))
cat(sprintf(
  "Of those, %d passed and %d failed — outcome depends entirely on which threshold applied.\n",
  sum(danger_zone$passed == 1),
  sum(danger_zone$passed == 0)
))

p7 <- tax_threshold %>%
  ggplot(aes(x = percent_yes, fill = zone)) +
  geom_histogram(binwidth = 2, color = "white", linewidth = 0.3) +
  geom_vline(xintercept = c(50, 55, 66.67), linetype = "dashed", color = "grey30") +
  scale_fill_manual(values = c(
    "Under 50%" = "grey65",
    "50-55% (majority, not Prop 39)" = ca_gold,
    "55-66.7% (Prop 39 OK, not 2/3)" = ca_blue,
    "Above 66.7% (clears all thresholds)" = ca_green
  )) +
  labs(
    title    = "The Threshold Landscape",
    subtitle = "Where California tax/bond measures land relative to approval thresholds",
    x = "Percent YES", y = "Count", fill = NULL
  ) +
  scale_x_continuous(labels = label_percent(scale = 1)) +
  theme(legend.position = "right")

ggsave(file.path(fig_dir, "fig7_threshold_landscape.png"),
       p7, width = 9, height = 5.5, dpi = 200)


###############################################################################
# ANALYSIS 9 — Has any county FLIPPED on a topic? (decade-over-decade change)
###############################################################################

cat("\n\n", "=" |> strrep(72), "\n")
cat("ANALYSIS 9: Counties that flipped on a topic over time\n")
cat("=" |> strrep(72), "\n\n")

decade_shift <- df %>%
  mutate(era = if_else(year <= 2010, "1998-2010", "2012-2024")) %>%
  group_by(county, topic, era) %>%
  summarize(
    n         = n(),
    pass_rate = mean(passed),
    avg_yes   = mean(percent_yes),
    .groups   = "drop"
  ) %>%
  filter(n >= 3) %>%
  pivot_wider(
    names_from  = era,
    values_from = c(n, pass_rate, avg_yes),
    names_sep   = "_"
  ) %>%
  filter(!is.na(`pass_rate_1998-2010`), !is.na(`pass_rate_2012-2024`)) %>%
  mutate(
    shift = `pass_rate_2012-2024` - `pass_rate_1998-2010`,
    yes_shift = `avg_yes_2012-2024` - `avg_yes_1998-2010`
  )

cat("Biggest shifts TOWARD passing (early → late):\n")
decade_shift %>%
  arrange(desc(shift)) %>%
  select(county, topic, starts_with("pass_rate"), shift) %>%
  slice_head(n = 10) %>%
  print()

cat("\nBiggest shifts AGAINST passing (early → late):\n")
decade_shift %>%
  arrange(shift) %>%
  select(county, topic, starts_with("pass_rate"), shift) %>%
  slice_head(n = 10) %>%
  print()


###############################################################################
# ANALYSIS 10 — Summary dashboard: the "personality" of each major county
###############################################################################

cat("\n\n", "=" |> strrep(72), "\n")
cat("ANALYSIS 10: County scorecards\n")
cat("=" |> strrep(72), "\n\n")

scorecards <- df %>%
  filter(county %in% top_counties) %>%
  group_by(county) %>%
  summarize(
    n_measures        = n(),
    years_covered     = paste(range(year), collapse = "-"),
    overall_pass_rate = mean(passed),
    avg_yes_pct       = mean(percent_yes),
    tax_pass_rate     = mean(passed[is_tax_or_bond], na.rm = TRUE),
    tax_avg_yes       = mean(percent_yes[is_tax_or_bond], na.rm = TRUE),
    tightest_race     = min(abs(percent_yes - 50)),
    n_supermaj_trap   = sum(passed == 0 & percent_yes >= 50),
    .groups           = "drop"
  ) %>%
  arrange(desc(overall_pass_rate))

cat("Top 20 counties — scorecard:\n")
scorecards %>%
  mutate(
    overall_pass_rate = sprintf("%.1f%%", overall_pass_rate * 100),
    avg_yes_pct       = sprintf("%.1f%%", avg_yes_pct),
    tax_pass_rate     = sprintf("%.1f%%", tax_pass_rate * 100),
    tax_avg_yes       = sprintf("%.1f%%", tax_avg_yes),
    tightest_race     = sprintf("%.1f pp", tightest_race)
  ) %>%
  print(n = 20)


###############################################################################
# Wrap up
###############################################################################

cat("\n\n", "=" |> strrep(72), "\n")
cat("FIGURES SAVED\n")
cat("=" |> strrep(72), "\n\n")
cat("All figures saved to: ", fig_dir, "/\n")
cat("  fig1_la_property_tax.png       — LA vs. rest on property taxes\n")
cat("  fig2_county_topic_heatmap.png  — 20 counties × 6 measure types\n")
cat("  fig3_tax_trend.png             — Tax pass rates over time\n")
cat("  fig4_regional_personality.png  — Regional voting patterns\n")
cat("  fig5_education_premium.png     — Education vs. non-ed measures\n")
cat("  fig6_county_timelines.png      — 8 key counties over time\n")
cat("  fig7_threshold_landscape.png   — Tax measures vs. approval thresholds\n")
cat("\nDone!\n")
