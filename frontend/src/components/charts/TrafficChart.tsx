import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { trafficSeries } from '../../utils/mockData'

export function TrafficChart(): React.JSX.Element {
  return (
    <div className="h-[280px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={trafficSeries}
          barGap={6}
          margin={{ top: 10, right: 4, left: -22, bottom: 0 }}
        >
          <CartesianGrid stroke="#253044" strokeDasharray="3 3" vertical={false} />
          <XAxis
            axisLine={false}
            dataKey="time"
            tick={{ fill: '#7f8ba3', fontSize: 11 }}
            tickLine={false}
          />
          <YAxis
            axisLine={false}
            tick={{ fill: '#7f8ba3', fontSize: 11 }}
            tickFormatter={(value) => `${value}`}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: '#151c2a',
              border: '1px solid #253044',
              borderRadius: 12,
              color: '#e8eef8',
              fontSize: 12,
            }}
            formatter={(value, name) => [
              `${value} Mbps`,
              name === 'inbound' ? 'Network IN' : 'Network OUT',
            ]}
            labelStyle={{ color: '#7f8ba3' }}
          />
          <Legend
            align="right"
            iconType="circle"
            iconSize={7}
            wrapperStyle={{ color: '#7f8ba3', fontSize: 11, paddingTop: 8 }}
            formatter={(value) => (value === 'inbound' ? 'Network IN' : 'Network OUT')}
          />
          <Bar dataKey="inbound" fill="#34d399" radius={[4, 4, 0, 0]} />
          <Bar dataKey="outbound" fill="#38bdf8" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
