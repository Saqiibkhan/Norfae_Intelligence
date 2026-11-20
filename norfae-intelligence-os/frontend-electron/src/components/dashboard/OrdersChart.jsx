import {

  ResponsiveContainer,

  BarChart,

  Bar,

  XAxis,

  YAxis,

  Tooltip,

  CartesianGrid

} from "recharts"


function OrdersChart({

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

          Orders Trend

        </h2>

        <p className="
          text-slate-400
        ">

          Daily operational order volume

        </p>

      </div>

      <div className="h-[400px]">

        <ResponsiveContainer
          width="100%"
          height="100%"
        >

          <BarChart data={data}>

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

            <Bar
              dataKey="orders"
              fill="#3b82f6"
              radius={[8, 8, 0, 0]}
            />

          </BarChart>

        </ResponsiveContainer>

      </div>

    </div>
  )
}

export default OrdersChart