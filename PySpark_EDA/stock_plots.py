from data_schema import Original_Schema
from upload_to_gcp import Upload_To_GCP

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.functions import when, col, max, min, avg, stddev, first
from pyspark.ml.stat import Correlation
from pyspark.ml.feature import VectorAssembler

from pyspark.sql.types import DoubleType

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import re

class EDA_Plots:
    def __init__(self):
        self.gcp_functions = Upload_To_GCP()

    def read_in_data_data_cleaning(self):
        spark = SparkSession.builder.appName("stock_clean").getOrCreate()
        sc = spark.sparkContext

        gcp_data_files = self.gcp_functions.list_blobs(bucket_name = "stock-sp500")
        clean_data_file_name = [x for x in gcp_data_files if re.match(r'Data/S&P_500_Clean_Data.csv/part*',x)][0]

        full_bucket_name = "gs://stock-sp500/"+clean_data_file_name

        og_schema = Original_Schema()
        clean_stock_schema = og_schema.clean_stock_data_schema()

        self.stock_df_clean = spark.read.csv(full_bucket_name,
                                             header = True,
                                             schema = clean_stock_schema).cache()

        return self.stock_df_clean

    def eda_category_counts(self):
        # Category Counts Data
        tot_count = self.stock_df_clean.count()

        cat2_counts = self.stock_df_clean\
            .groupBy('Category2')\
                .count()\
                    .withColumn('Propotion %', F.round((F.col('count')/tot_count),2))\
                        .orderBy('count', ascending=False)


        cat3_counts = self.stock_df_clean\
            .groupBy('Category3')\
                .count()\
                    .withColumn('Propotion %', F.round((F.col('count')/tot_count),2))\
                        .orderBy('count', ascending=False)


        sector_counts = self.stock_df_clean\
            .groupBy('GICS Sector')\
                .count()\
                    .withColumn('Propotion %', F.round((F.col('count')/tot_count),2))\
                        .orderBy('count', ascending=False)

        year_counts = self.stock_df_clean\
            .groupBy('year')\
                .count()\
                    .withColumn('Propotion %', F.round((F.col('count')/tot_count),2))\
                        .orderBy('year', ascending=True)

        # Category Counts Data to Pandas Dataframe to plot in Matplotlib
        cat2_counts_df = cat2_counts.toPandas()
        cat2_counts_df['str Prop2'] = cat2_counts_df['Propotion %'] * 100
        cat2_counts_df['str Prop2'] = cat2_counts_df['str Prop2'].round(2)
        cat2_counts_df['str Prop2'] = cat2_counts_df['str Prop2'].astype(str) + '%'

        cat3_counts_df = cat3_counts.toPandas()
        cat3_counts_df['str Prop3'] = cat3_counts_df['Propotion %'] * 100
        cat3_counts_df['str Prop3'] = cat3_counts_df['str Prop3'].round(2)
        cat3_counts_df['str Prop3'] = cat3_counts_df['str Prop3'].astype(str) + '%'

        sector_counts_df = sector_counts.toPandas()
        sector_counts_df['str Prop4'] = sector_counts_df['Propotion %'] * 100
        sector_counts_df['str Prop4'] = sector_counts_df['str Prop4'].round(2)
        sector_counts_df['str Prop4'] = sector_counts_df['str Prop4'].astype(str) + '%'

        year_counts_df = year_counts.toPandas()
        year_counts_df['str Prop5'] = year_counts_df['Propotion %'] * 100
        year_counts_df['str Prop5'] = year_counts_df['str Prop5'].round(2)
        year_counts_df['str Prop5'] = year_counts_df['str Prop5'].astype(str) + '%'

        # Creating Figure for Category Counts
        fig, axes = plt.subplots(2,2, figsize=(15, 10), sharey=False)
        fig.suptitle('Category EDA Counts')

        # Category2
        sns.barplot(ax=axes[0,0], x=cat2_counts_df['Category2'], y=cat2_counts_df['count'])
        axes[0,0].set_title("Category2 Stock Types")
        axes[0,0].bar_label(axes[0,0].containers[0], labels = cat2_counts_df['str Prop2'])
        axes[0,0].set(xlabel=None)

        # Category3
        sns.barplot(ax=axes[0,1], x=cat3_counts_df['Category3'], y=cat3_counts_df['count'])
        axes[0,1].set_title("Category3 Stock Types")
        axes[0,1].bar_label(axes[0,1].containers[0], labels = cat3_counts_df['str Prop3'])
        axes[0,1].set(xlabel=None)

        # Category3
        sns.barplot(ax=axes[1,0], x=sector_counts_df['GICS Sector'], y=sector_counts_df['count'])
        axes[1,0].set_title("GICS Stock Types")
        axes[1,0].bar_label(axes[1,0].containers[0], labels = sector_counts_df['str Prop4'])
        axes[1,0].tick_params(labelrotation=90)
        axes[1,0].set(xlabel=None)

        # Category3
        sns.barplot(ax=axes[1,1], x=year_counts_df['year'], y=year_counts_df['count'])
        axes[1,1].set_title("GICS Stock Types")
        axes[1,1].bar_label(axes[1,1].containers[0], labels = year_counts_df['str Prop5'])
        axes[1,1].tick_params(labelrotation=90)
        axes[1,1].set(xlabel=None)

        fig.tight_layout()
        fig.savefig("category_counts.png")

        # Uploading this figure up to GCP bucket
        self.gcp_functions.upload_filename(bucket_name="stock-sp500", 
                                           file_name= "category_counts.png", 
                                           destination_blob_name="EDA_Plots/category_counts.png")


    def best_day_of_week_stocks(self):
        # Stock prices by day of the week plot
        best_time_to_buy = self.stock_df_clean.groupBy('day_of_week')\
            .agg(F.round(min('Close'), 2).alias('Close_min'),\
                F.round(max('Close'), 2).alias('Close_max'),\
                    F.round(avg('Close'), 2).alias('Close_avg'),\
                        F.round(F.percentile_approx("Close", 0.5), 2).alias("Close_med"),\
                            F.round(stddev('Close'), 2).alias('Close_stddev'))\
                                .orderBy(when(col("day_of_week") == "Monday", 1)\
                                    .when(col("day_of_week") == "Tuesday", 2)\
                                        .when(col("day_of_week") == "Wednesday", 3)\
                                            .when(col("day_of_week") == "Thursday", 4)\
                                                .when(col("day_of_week") == "Friday", 5))

        # Stock close prices by day of week to Pandas Dataframe to plot in Matplotlib
        best_time_to_buy_df = best_time_to_buy.toPandas()
        best_time_to_buy_df["Close_med"] = best_time_to_buy_df["Close_med"].astype(float).round(2)
        best_time_to_buy_df["Close_avg"] = best_time_to_buy_df["Close_avg"].astype(float).round(2)

        fig, ax1 = plt.subplots(figsize=(12,6))
        best_day_plot = best_time_to_buy_df[["day_of_week", "Close_avg", "Close_med"]].plot.bar(x='day_of_week', ax=ax1)

        for p in best_day_plot.patches:
            best_day_plot.annotate(format(p.get_height()),
                        (p.get_x() + p.get_width() / 2., p.get_height()),
                        ha='center', va='center',
                        xytext=(0, 9),
                        textcoords='offset points')

        plt.tight_layout()
        plt.xticks(rotation=45, ha="right")
        plt.xlabel("Day of the Week")
        plt.ylabel("Close Price")
        plt.title("Close Price by Day of the Week")
        plt.legend(loc="upper right", framealpha=0.15)
        plt.savefig("day_of_week_stock_counts.png")

        # Uploading this figure up to GCP bucket
        self.gcp_functions.upload_filename(bucket_name="stock-sp500", 
                                           file_name= "day_of_week_stock_counts.png", 
                                           destination_blob_name="EDA_Plots/day_of_week_stock_counts.png")

    def most_valuable_gcis(self):
        # Most valuable by GCIS
        best_sector = self.stock_df_clean.groupBy('GICS Sector')\
            .agg(F.round(avg('Close'), 2).alias('Close_avg'),\
                F.round(F.percentile_approx("Close", 0.5), 2).alias("Close_med"),\
                    F.round(stddev('Close'), 2).alias('Close_stddev'))
       
        # Stock Close Prices by GCIS sector to Pandas dataframe to plot in matplotlib
        best_sector_df = best_sector.toPandas()
        best_sector_df.sort_values(by = "Close_avg", inplace = True, ascending = False)
        best_sector_df.reset_index(inplace = True, drop = True)
        best_sector_df["Close_med"] = best_sector_df["Close_med"].astype(float).round(2)
        best_sector_df["Close_avg"] = best_sector_df["Close_avg"].astype(float).round(2)

        # Creating 
        fig, ((ax1), (ax2)) = plt.subplots(2,1,figsize=(12,12))
        best_sect_plot1 = best_sector_df[["GICS Sector", "Close_avg", "Close_med"]].plot.bar(x='GICS Sector', ax=ax1)
        for p in best_sect_plot1.patches:
            best_sect_plot1.annotate(format(p.get_height()),
                        (p.get_x() + p.get_width() / 2., p.get_height()),
                        ha='center', va='center',
                        xytext=(0, 9),
                        textcoords='offset points')    
        ax1.set_title('Close Price by GICS Sector')
        ax1.set_xlabel('')
        ax1.set_ylabel('Close Price')    
        ax1.legend(['Close Average', 'Close Median']) 
            
        best_sect_plot2 = best_sector_df[["GICS Sector", "Close_stddev"]].plot.bar(x='GICS Sector', ax=ax2)   
        for p in best_sect_plot2.patches:
            best_sect_plot2.annotate(format(p.get_height()),
                        (p.get_x() + p.get_width() / 2., p.get_height()),
                        ha='center', va='center',
                        xytext=(0, 9),
                        textcoords='offset points')  
        ax2.set_title('Standard Deviation by GICS Sector')
        ax2.set_xlabel('')
        ax2.set_ylabel('Close Price')
        ax2.legend().set_visible(False)
            
        plt.tight_layout()
        plt.savefig("gcis_close.png")

        # Uploading this figure up to GCP bucket
        self.gcp_functions.upload_filename(bucket_name="stock-sp500", 
                                           file_name= "gcis_close.png", 
                                           destination_blob_name="EDA_Plots/gcis_close.png")


    def daily_returns_by_sector(self):
        # Daily Returns by Sector
        dr_by_sector = self.stock_df_clean.groupBy('GICS Sector')\
            .agg(F.round(avg('daily_return'), 2).alias('dr_avg'),\
                F.round(F.percentile_approx("daily_return", 0.5), 2).alias("dr_med"),\
                    F.round(stddev('daily_return'), 2).alias('dr_stddev'))

        avg_by_symbol = self.stock_df_clean.groupBy('Symbol')\
            .agg(F.round(avg('Open'), 2).alias('open_avg'),\
                F.round(avg('High'), 2).alias('high_avg'),\
                    F.round(avg('Low'), 2).alias('low_avg'),\
                        F.round(avg('Close'), 2).alias('close_avg'),\
                            F.round(avg('Adj Close'), 2).alias('adj_close_avg'),\
                                F.round(avg('Volume'), 2).alias('volume_avg'),\
                                    F.round(avg('daily_return'), 2).alias('dr_avg'),\
                                        F.round(avg('cum_return'), 2).alias('cum_avg'))

        med_by_symbol = self.stock_df_clean.groupBy('Symbol')\
            .agg(F.round(F.percentile_approx("Open", 0.5), 2).alias("open_med"),\
                F.round(F.percentile_approx("High", 0.5), 2).alias("high_med"),\
                    F.round(F.percentile_approx("Low", 0.5), 2).alias("low_med"),\
                        F.round(F.percentile_approx("Close", 0.5), 2).alias("close_med"),\
                            F.round(F.percentile_approx("Adj Close", 0.5), 2).alias("adj_close_med"),\
                                F.round(F.percentile_approx("Volume", 0.5), 2).alias("volume_med"),\
                                    F.round(F.percentile_approx("daily_return", 0.5), 2).alias("dr_med"),\
                                        F.round(F.percentile_approx("cum_return", 0.5), 2).alias("cum_med"))


    def stock_symbol_correlation_plot(self):
        counts_by_symbol = self.stock_df_clean.groupBy("Symbol").count().sort(col("count").desc())
        max_count = int(np.array(counts_by_symbol.select([max("count")]).collect()).reshape(-1)[0])

        remove_symbols2 = counts_by_symbol.filter(counts_by_symbol['count'] < max_count)
        remove_symbols2_arr = np.array(remove_symbols2.select('Symbol').collect()).reshape(-1)

        corr_stock_df = self.stock_df_clean.select("*")

        for value in remove_symbols2_arr:
            cond = (F.col('Symbol') == value)
            corr_stock_df = corr_stock_df.filter(~cond)

        stock_symbol_corr = corr_stock_df.groupBy("Date").pivot("Symbol").agg(avg("Close"))
        stock_symbol_corr = stock_symbol_corr.orderBy('Date', ascending=True)
        

        double_cols = [f.name for f in stock_symbol_corr.schema.fields if isinstance(f.dataType, DoubleType)]
        integer_df = stock_symbol_corr[[double_cols]]
        integer_df_drop_na = integer_df.na.drop("any")

        vector_col = "corr_features"
        assembler = VectorAssembler(inputCols = integer_df_drop_na.columns, 
                                    outputCol = vector_col)
        df_vector = assembler.transform(integer_df_drop_na).select(vector_col)

        matrix = Correlation.corr(df_vector, vector_col).collect()[0][0]
        # corrmatrix = matrix.toArray().tolist()
        corrmatrix = matrix.toArray()



        # Uncomment below to plot this, just chnage the name from rows to corrmatrix
        fig, ax = plt.subplots(figsize=(15,15))
        heatmap = ax.pcolor(corrmatrix, cmap=plt.cm.Blues)

        # put the major ticks at the middle of each cell
        ax.set_xticks(np.arange(corrmatrix.shape[0])+0.5, minor=False)
        ax.set_yticks(np.arange(corrmatrix.shape[1])+0.5, minor=False)

        # want a more natural, table-like display
        ax.invert_yaxis()
        ax.xaxis.tick_top()

        ax.set_xticklabels(double_cols, minor=False)
        ax.set_yticklabels(double_cols, minor=False)
        plt.savefig("stock_corr_plots.png")

        # Uploading this figure up to GCP bucket
        self.gcp_functions.upload_filename(bucket_name="stock-sp500", 
                                           file_name= "stock_corr_plots.png", 
                                           destination_blob_name="EDA_Plots/stock_corr_plots.png")