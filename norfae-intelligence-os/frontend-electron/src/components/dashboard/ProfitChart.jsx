import {

  ResponsiveContainer,

  AreaChart,

  Area,

  XAxis,

  YAxis,

  Tooltip,

  CartesianGrid

} from "recharts"


function ProfitChart({

  data
}) {

  return (

    <div className="
      bg-gradient-to-br
      from-slate-900
      to-slate-950
      border
      border-slate-800
      rounded-3xl
      p-8
    ">

      <div className="mb-8">

        <h2 className="
          text-3xl
          font-black
          text-white
          mb-2
        ">

          Profit Trend

        </h2>

        <p className="
          text-slate-400
        ">

          Net profitability over time

        </p>

      </div>

      <div className="h-[400px]">

        <ResponsiveContainer
          width="100%"
          height="100%"
        >

          <AreaChart data={data}>

            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#1e293b"
            />

            <XAxis
              dataKey="date"
              stroke="#94a3b8"
            />

            <YAxis
              stroke="#94a3b8"
            />

            <Tooltip />

            <Area
              type="monotone"
              dataKey="profit"
              stroke="#22c55e"
              fill="#22c55e"
              fillOpacity={0.2}
              strokeWidth={4}
            />

          </AreaChart>

        </ResponsiveContainer>

      </div>

    </div>
  )
}

export default ProfitChart