import {

  ResponsiveContainer,

  LineChart,

  Line,

  XAxis,

  YAxis,

  Tooltip,

  CartesianGrid

} from "recharts"


function DeliveryChart({

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

          Delivery Performance

        </h2>

        <p className="
          text-slate-400
        ">

          Delivered order trend analytics

        </p>

      </div>

      <div className="h-[400px]">

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

            <Tooltip />

            <Line
              type="monotone"
              dataKey="delivered"
              stroke="#eab308"
              strokeWidth={4}
            />

          </LineChart>

        </ResponsiveContainer>

      </div>

    </div>
  )
}

export default DeliveryChart