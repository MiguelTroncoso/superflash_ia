import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { loadSeries } from '../../utils/mockData'

export function SystemLoadChart(): React.JSX.Element {
  return (
    <div className="h-[280px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={loadSeries} margin={{ top: 10, right: 4, left: -22, bottom: 0 }}>
          <defs>
            <linearGradient id="cpuGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#38bdf8" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="memoryGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.28} />
              <stop offset="100%" stopColor="#a78bfa" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#253044" strokeDasharray="3 3" vertical={false} />
          <XAxis
            axisLine={false}
            dataKey="time"
            tick={{ fill: '#7f8ba3', fontSize: 11 }}
            tickLine={false}
          />
          <YAxis
            axisLine={false}
            domain={[0, 100]}
            tick={{ fill: '#7f8ba3', fontSize: 11 }}
            tickFormatter={(value) => `${value}%`}
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
            formatter={(value, name) => [`${value}%`, name === 'cpu' ? 'CPU' : 'Memory']}
            labelStyle={{ color: '#7f8ba3' }}
          />
          <Legend
            align="right"
            iconType="circle"
            iconSize={7}
            wrapperStyle={{ color: '#7f8ba3', fontSize: 11, paddingTop: 8 }}
            formatter={(value) => (value === 'cpu' ? 'CPU' : 'Memory')}
          />
          <Area
            type="monotone"
            dataKey="cpu"
            stroke="#38bdf8"
            strokeWidth={2}
            fill="url(#cpuGradient)"
          />
          <Area
            type="monotone"
            dataKey="memory"
            stroke="#a78bfa"
            strokeWidth={2}
            fill="url(#memoryGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
