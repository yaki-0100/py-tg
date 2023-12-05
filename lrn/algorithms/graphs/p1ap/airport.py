from graphframes import *
from pyspark.sql import SparkSession
from pyspark.sql.types import *
from pyspark.sql import functions as f
import matplotlib
import matplotlib.pyplot as plt

matplotlib.use('TkAgg')
plt.style.use('fivethirtyeight')
spark = SparkSession()

nodes = spark.read.csv('../data/airports.csv', header=False)
cleaned_nodes = nodes.select('_c1', '_c3', '_c5', '_c6', '_c7').filter("_c3 = 'United States'").withColumnRenamed('_c1',
                                                                                                                  'name').withColumnRenamed(
    '_c4', 'id').withColumnRenamed('_c6', 'latitude').withColumnRenamed('_c7', 'longitude').drop('_c3')
cleaned_nodes = cleaned_nodes[cleaned_nodes['id'] != '\\N']
relationships = spark.read.csv('../data/sw-relationships.csv', header=True)
cleaned_relationships = relationships.select('ORIGIN', 'DEST', 'FL_DATE', 'DEP_DELAY', 'ARR_DELAY', 'DISTANCE',
                                             'TAIL_NUM', 'FL_NUM', 'CRS_DEP_TIME', 'CRS_ARR_TIME',
                                             'UNIQUE_CARRIER').withColumnRenamed('ORIGIN', 'src').withColumnRenamed(
    'DEST', 'dst').withColumnRenamed('DEP_DELAY', 'deptDelay').withColumnRenamed('ARR_DELAY',
                                                                                 'arrDelay').withColumnRenamed(
    'TAIL_NUM', 'tailNumber').withColumnRenamed('FL_NUM', 'flightNumber').withColumnRenamed('FL_DATE',
                                                                                            'data').withColumnRenamed(
    'CRS_DEP_TIME', 'time').withColumnRenamed('CRS_ARR_TIME', 'arrivalTime').withColumnRenamed('DISTANCE',
                                                                                               'distance').withColumnRenamed(
    'UNIQUE_CARRIER', 'airline').withColumn('deptDelay', f.col('deptDelay').cast(FloatType())).withColumn('arrDelay',
                                                                                                          f.col(
                                                                                                              'arrDelay').cast(
                                                                                                              FloatType())).withColumn(
    'time', f.col('time').cast(IntegerType())).withColumn('arrivalTime', f.col('arrivalTime').cast(IntegerType()))
g = GraphFrame(cleaned_nodes, cleaned_relationships)
airlines_reference = spark.read.csv('../data/airlines.csv').select('_c1', '_c3').withColumnRenamed('_c1',
                                                                                                   'name').withColumnRenamed(
    '_c3', 'code')
airlines_reference = airlines_reference[airlines_reference['code'] != 'null']
df = spark.read.option('multiline', 'true').json('../data/airlines.json')
dummy_df = spark.createDataFrame([('test', 'test')], ['code', 'name'])
for code in df.schema.fieldNames():
    temp_df = df.withColumn('code', f.lit(code)).withColumn('name', df[code])
    tdf = temp_df.select('code', 'name')
    dummy_df = dummy_df.union(tdf)
g.vertices.count()
g.edges.count()
g.edges.groupBy().max('deptDelay').show()

g.edges.groupBy().max('deptDelay').show()
airports_degree = g.outDegrees.withColumnRenamed('id', 'oId')
full_airports_degree = airports_degree.join(g.vertices, airports_degree.oId == g.vertices.id).sort('outDegree',
                                                                                                   ascending=False).select(
    'id', 'name', 'outDegree')
ax = full_airports_degree.toPandas().head(10).plot(kind='bar', x='id', y='outDegree', legend=None)
ax.xaxis.set_label_text('')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
plt.savefig('/tmp/airports.svg')
plt.close()

delayed_flights = g.edges.filter("src = 'ORD' and deptDelay > 0").groupBy('dst').agg(f.avg('deptDelay'),
                                                                                     f.count('deptDelay')).withColumn(
    'averageDelay', f.round(f.col('avg(deptDelay)'), 2)).withColumn('numberOFDelays', f.col('count(deptDelay)'))
delayed_flights.join(g.vertices, delayed_flights.dst == g.vertices.id).sort(f.desc('averageDelay')).select('dst',
                                                                                                           'name',
                                                                                                           'averageDelay',
                                                                                                           'numberOfDelays').show(
    n=10, truncate=False)
from_expr = 'id = "ORD"'
to_expr = 'id = "CKB"'
ord_to_ckb = g.bfs(from_expr, to_expr)
ord_to_ckb = ord_to_ckb.select(f.col('e0.date'), f.col('e0.time'), f.col('e0.flightNumber'), f.col('e0.deptDelay'))
ax = ord_to_ckb.sort('date').toPandas().plot(kind='bar', x='date', y='deptDelay', legend=None)
ax.xaxis.set_label_text('')
plt.tight_layout()
plt.show()
plt.savefig('/tmp/ord-ckb.svg')
plt.close()

motifs = g.find('(a)-[ab]->(b); (b)-[bc]->(c)').filter("""
    (b.id = 'SFO') and
    (ab.date = '2018-05-11' and bc.date = '2018-05-11') and
    (ab.arrDelay > 30 or bc.deptDelay > 30) and
    (ab.flightNumber = bc.flightNumber) and
    (ab.airline = bc.airline) and
    (ab.time < bc.time)
""")


def sum_dist(d1, d2):
    return sum([value for value in [d1, d2] if value is not None])


sum_dist_udf = f.udf(sum_dist, FloatType())
result = motifs.withColumn('delta', motifs.bc.deptDelay - motifs.ab.arrDelay).select('ab', 'bc', 'delta').sort('delta',
                                                                                                               ascending=False)
result.select(f.col('ab.src').alias('a1'), f.col('ab.time').alias('a1DeptTime'), f.col('ab.arrDelay'),
              f.col('ab.dst').alias('a2'), f.col('bc.time').alias('a2DeptTime'), f.col('bc.deptDelay'),
              f.col('bc.dst').alias('a3'), f.col('ab.airline'), f.col('ab.flightNumber'), f.col('delta')).show()
