# ==============================================================
# Loan Approval Classification Analysis and Modeling in R
# ==============================================================

# 1. Load Required Libraries
suppressPackageStartupMessages({
  library(tidyverse)      # For data manipulation and visualization
  library(caret)          # For machine learning workflows
  library(randomForest)   # For Random Forest modeling
  library(pROC)           # For ROC/AUC evaluation
})

# 2. Load the Dataset
# Data lives at data/raw/loan_data.csv relative to the project root.
# Run scripts/00_download_data.sh first if the file does not exist.
cat("Loading data...\n")
df <- read_csv("data/raw/loan_data.csv", show_col_types = FALSE)

# Display initial data structure
cat("Initial dataset dimensions:", dim(df)[1], "rows and", dim(df)[2], "columns\n")

# 3. Data Cleaning & Preprocessing
cat("\n--- Data Cleaning ---\n")

# The dataset author explicitly mentions an anomaly: age > 100. Let's filter it out.
df <- df %>%
  filter(person_age <= 100)

# Check for missing values and drop them (or you could impute them)
cat("Missing values per column before cleaning:\n")
print(colSums(is.na(df)))
df <- drop_na(df)

# Convert character/categorical columns and the target variable to factors
categorical_cols <- c(
  "person_gender", "person_education", "person_home_ownership",
  "loan_intent", "previous_loan_defaults_on_file", "loan_status"
)

df <- df %>%
  mutate(across(all_of(categorical_cols), as.factor))

# Rename target factor levels for `caret` compatibility
# Caret can have issues with factor levels named "0" and "1"
levels(df$loan_status) <- c("Rejected", "Approved")

cat("Cleaned dataset dimensions:", dim(df)[1], "rows and", dim(df)[2], "columns\n")

# 4. Exploratory Data Analysis (EDA)
cat("\n--- Generating EDA Plots ---\n")

# Plot 1: Target Variable Distribution
p1 <- ggplot(df, aes(x = loan_status, fill = loan_status)) +
  geom_bar(alpha = 0.8, color = "black") +
  theme_minimal() +
  scale_fill_manual(values = c("Rejected" = "#e74c3c", "Approved" = "#2ecc71")) +
  labs(title = "Loan Approval Status Distribution", x = "Status", y = "Count")
print(p1)

# Plot 2: Loan Amount vs. Loan Intent
p2 <- ggplot(df, aes(x = reorder(loan_intent, loan_amnt, FUN = median), y = loan_amnt, fill = loan_status)) +
  geom_boxplot(alpha = 0.7, outlier.shape = NA) +
  theme_minimal() +
  coord_cartesian(ylim = c(0, 35000)) + # Limit y-axis to ignore extreme outliers in plot
  theme(axis.text.x = element_text(angle = 45, hjust = 1)) +
  labs(title = "Loan Amount by Loan Intent", x = "Loan Intent", y = "Loan Amount")
print(p2)

# Plot 3: Credit Score vs Interest Rate
p3 <- ggplot(df, aes(x = credit_score, y = loan_int_rate, color = loan_status)) +
  geom_point(alpha = 0.4) +
  theme_minimal() +
  scale_color_manual(values = c("Rejected" = "#e74c3c", "Approved" = "#2ecc71")) +
  labs(title = "Credit Score vs Loan Interest Rate", x = "Credit Score", y = "Interest Rate (%)")
print(p3)

# 5. Train/Test Data Split
set.seed(42) # For reproducibility
train_index <- createDataPartition(df$loan_status, p = 0.8, list = FALSE)
train_data <- df[train_index, ]
test_data  <- df[-train_index, ]

cat("\nTraining set size:", nrow(train_data), "rows\n")
cat("Testing set size:", nrow(test_data), "rows\n")

# 6. Machine Learning Modeling

# --- Model A: Logistic Regression ---
cat("\n--- Training Logistic Regression Model ---\n")
logit_model <- train(
  loan_status ~ .,
  data = train_data,
  method = "glm",
  family = "binomial",
  trControl = trainControl(method = "cv", number = 5)
)

logit_preds <- predict(logit_model, test_data)
logit_cm <- confusionMatrix(logit_preds, test_data$loan_status)
cat("Logistic Regression Accuracy:", round(logit_cm$overall["Accuracy"] * 100, 2), "%\n")

# --- Model B: Random Forest ---
cat("\n--- Training Random Forest Model ---\n")
# Using randomForest package directly for faster execution tree building
rf_model <- randomForest(
  loan_status ~ .,
  data = train_data,
  ntree = 100,
  importance = TRUE
)

rf_preds <- predict(rf_model, test_data)
rf_cm <- confusionMatrix(rf_preds, test_data$loan_status)
cat("Random Forest Accuracy:", round(rf_cm$overall["Accuracy"] * 100, 2), "%\n")

# 7. Model Evaluation & Feature Importance

# Plot Variable Importance from the Random Forest Model
cat("\n--- Plotting Feature Importance & ROC Curve ---\n")
varImpPlot(rf_model, main = "Random Forest Feature Importance", pch = 16, col = "darkblue")

# ROC Curve for Random Forest
# Get raw probabilities for the "Approved" class
rf_probs <- predict(rf_model, test_data, type = "prob")[, "Approved"]

roc_curve <- roc(
  response = test_data$loan_status,
  predictor = rf_probs,
  levels = c("Rejected", "Approved")
)

# Plot ROC
plot(roc_curve,
     main = paste("Random Forest ROC Curve\nAUC =", round(auc(roc_curve), 3)),
     col = "#2980b9",
     lwd = 3)

cat("\nAnalysis complete! Check your plot viewer for the generated visualizations.\n")
