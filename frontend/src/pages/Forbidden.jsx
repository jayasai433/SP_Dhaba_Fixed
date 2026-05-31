import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ShieldOff } from "lucide-react";

export default function Forbidden() {
  return (
    <div className="min-h-screen flex items-center justify-center p-6" data-testid="forbidden-page">
      <div className="text-center max-w-md">
        <div className="mx-auto h-16 w-16 rounded-2xl bg-red-100 text-red-600 flex items-center justify-center mb-4">
          <ShieldOff size={28} />
        </div>
        <h1 className="font-display text-3xl font-bold text-slate-900">Access denied</h1>
        <p className="mt-2 text-slate-600">You don't have permission to view this page.</p>
        <Link to="/"><Button className="mt-6 rounded-full bg-orange-600 hover:bg-orange-700" data-testid="back-home-btn">Go to home</Button></Link>
      </div>
    </div>
  );
}
