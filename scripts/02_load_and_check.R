library(tidyverse)

df <- read_csv("data/raw/loan_data.csv", show_col_types = FALSE)

glimpse(df)
summary(df)

# quick missingness scan
df %>% summarise(across(everything(), ~ sum(is.na(.))))
