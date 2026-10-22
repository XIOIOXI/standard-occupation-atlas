import React, { useEffect, useMemo, useRef } from 'react';
import * as echarts from 'echarts/core';
import { MapChart } from 'echarts/charts';
import { TooltipComponent, VisualMapComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import chinaGeoJson from 'china-geojson/src/geojson/china.json';
import { getLocationDistribution } from '../lib/locationDistribution.js';

echarts.use([MapChart, TooltipComponent, VisualMapComponent, CanvasRenderer]);
echarts.registerMap('china-provinces', chinaGeoJson);

export default function LocationDistributionMap({ records, selectedProvince = '', onSelectProvince }) {
  const hostRef = useRef(null);
  const chartRef = useRef(null);
  const { provinces, identifiableRecords } = useMemo(() => getLocationDistribution(records), [records]);

  useEffect(() => {
    const chart = echarts.init(hostRef.current, null, { renderer: 'canvas' });
    chartRef.current = chart;
    const max = Math.max(1, ...provinces.map(province => province.value));
    chart.setOption({
      animationDuration: 260,
      animationEasing: 'cubicOut',
      tooltip: {
        trigger: 'item', backgroundColor: '#f3f3ee', borderWidth: 0,
        textStyle: { color: '#111', fontSize: 12 },
        formatter: params => `${params.name}<br/><strong>${params.value || 0}</strong> 条招聘岗位记录含该省 / 地区地点`,
      },
      visualMap: {
        min: 0, max, calculable: false, orient: 'horizontal', left: 10, bottom: 2, itemWidth: 18, itemHeight: 8,
        text: ['地点提及多', '少'], textGap: 8, textStyle: { color: '#536157', fontSize: 10 },
        inRange: { color: ['#f2f6e9', '#e0edc8', '#afce8f', '#5e8750'] },
      },
      series: [{
        type: 'map', map: 'china-provinces', roam: false, silent: false, zoom: 1.08, top: 4, bottom: 36,
        label: { show: false },
        emphasis: { label: { show: true, color: '#111', fontWeight: 700 }, itemStyle: { areaColor: '#dbe7ff', borderColor: '#fff', borderWidth: 1.2 } },
        selectedMode: false,
        select: { label: { show: true, color: '#172c1d' }, itemStyle: { areaColor: '#dbe7ff', borderColor: '#1647ff', borderWidth: 2 } },
        itemStyle: { areaColor: '#edf2e8', borderColor: '#a5b49d', borderWidth: 0.75 }, data: provinces,
      }],
    });
    chart.on('click', params => { if (params.componentType === 'series') onSelectProvince?.(params.name); });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(hostRef.current);
    return () => { observer.disconnect(); chart.dispose(); chartRef.current = null; };
  }, [provinces, onSelectProvince]);

  useEffect(() => {
    chartRef.current?.setOption({ series: [{ data: provinces.map(item => ({ ...item, selected: item.name === selectedProvince })) }] });
  }, [provinces, selectedProvince, onSelectProvince]);

  return <section className="location-distribution" aria-labelledby="location-distribution-title">
    <div className="location-distribution-heading">
      <div><h2 id="location-distribution-title">招聘地点分布</h2></div>
    </div>
    <div className="province-map" ref={hostRef} role="img" aria-label={`中国省级招聘地点分布图；${identifiableRecords} 条招聘岗位记录含可识别地点`} />
  </section>;
}
