import {

  ResponsiveContainer,

  LineChart,

  Line,

  XAxis,

  YAxis,

  Tooltip,

  CartesianGrid

} from "recharts"


function RevenueChart({

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
      mt-10
    ">

      {/* HEADER */}

      <div className="mb-8">

        <h2 className="
          text-3xl
          font-black
          text-white
          mb-2
        ">

          Revenue Trend

        </h2>

        <p className="
          text-slate-400
          text-lg
        ">

          Revenue analytics over time

        </p>

      </div>

      {/* CHART */}

      <div className="h-[420px]">

        <ResponsiveContainer
          width="100%"
          height="100%"
        >

          <LineChart data={data}>

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

            <Tooltip
              contentStyle={{
                backgroundColor: "#020617",
                border: "1px solid #1e293b",
                borderRadius: "16px",
                color: "#fff"
              }}
            />

            <Line
              type="monotone"
              dataKey="revenue"
              stroke="#06b6d4"
              strokeWidth={4}
              dot={{
                r: 5
              }}
              activeDot={{
                r: 8
              }}
            />

          </LineChart>

        </ResponsiveContainer>

      </div>

    </div>
  )
}

export default RevenueChart