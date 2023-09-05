```shell
python .\randomTrips.py -n F:\研究生\双智\SimPlatform\data\network\changjidong_yutangnan_only.net.xml ` 
-o F:\研究生\双智\SimPlatform\data\network\route\isolated\demand_high.trip.xml `
 --fringe-factor max --binomial 3 --period 1 -e 4000 -l --vehicle-class passenger `
  --trip-attributes='maxSpeed=\"13.89\" lcKeepRight=\"0\" laneChangeModel=\"LC2013\" departLane=\"best\" departSpeed=\"max\"'
```

```shell
duarouter -n F:\研究生\双智\SimPlatform\data\network\changjidong_yutangnan_only.net.xml `
 --route-files F:\研究生\双智\SimPlatform\data\network\route\isolated\demand_high.trip.xml `
  -o F:\研究生\双智\SimPlatform\data\network\route\isolated\demand_high.rou.xml -s 4000
```
