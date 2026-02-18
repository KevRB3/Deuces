#!/usr/bin/env bash
mkdir -p data/raw
kaggle datasets download -d taweilo/loan-approval-classification-data -p data/raw --unzip
