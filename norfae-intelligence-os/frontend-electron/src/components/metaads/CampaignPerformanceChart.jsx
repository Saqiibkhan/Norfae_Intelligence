import {
  BarChart,
  Bar,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";

export default function CampaignPerformanceChart({ campaigns }) {
  return (
    <div className="bg-slate-900 rounded-3xl p-6 border border-slate-800">
      <h3 className="text-xl font-bold mb-6">Campaign Performance</h3>

      <ResponsiveContainer width="100%" height={350}>
        <BarChart data={campaigns}>
          <XAxis dataKey="campaign_name" />

          <YAxis />

          <Tooltip />

          <Bar dataKey="instagram_messages" fill="#06b6d4" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
