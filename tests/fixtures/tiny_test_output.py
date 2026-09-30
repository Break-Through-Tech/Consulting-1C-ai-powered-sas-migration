import pandas as pd

# Create a new dataset from the input dataset and calculate new_var
test = input_df.copy()
test['new_var'] = test['old_var'] * 2