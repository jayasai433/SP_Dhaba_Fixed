import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import axios from "axios";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { toast } from "sonner";
import { formatApiError } from "@/lib/api";
import { Eye, EyeOff, LogIn } from "lucide-react";

// Background image — Indian food/dhaba themed (Unsplash, free to use)
const BG = "https://images.unsplash.com/photo-1567188040759-fb8a883dc6d8?w=1200&q=80";
// Fallback: orange gradient if image fails to load

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const loc = useLocation();
  const [bizName, setBizName] = useState("SP Royal Punjabi Family Dhaba");

  useEffect(() => {
    const backendUrl = process.env.REACT_APP_BACKEND_URL;
    if (backendUrl) {
      axios.get(`${backendUrl}/api/business-profile`)
        .then(({ data }) => { if (data?.name) setBizName(data.name); })
        .catch(() => {}); // use default if fetch fails
    }
  }, []);

  useEffect(() => {
    if (user) {
      const to = user.role === "viewer" ? "/display" : (user.role === "staff" ? "/stock" : "/dashboard");
      navigate(to, { replace: true });
    }
  }, [user, navigate]);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const u = await login(email.trim().toLowerCase(), password);
      toast.success(`Welcome, ${u.name}`);
      const from = loc.state?.from?.pathname;
      const dest = from || (u.role === "viewer" ? "/display" : (u.role === "staff" ? "/stock" : "/dashboard"));
      navigate(dest, { replace: true });
    } catch (err) {
      toast.error(formatApiError(err, "Login failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex flex-col md:flex-row" data-testid="login-page">
      {/* Visual side */}
      <div className="hidden md:block flex-1 relative">
        <img
          src={BG}
          alt=""
          className="absolute inset-0 w-full h-full object-cover"
          onError={(e) => { e.target.style.display = "none"; }}
        />
        <div className="absolute inset-0 bg-gradient-to-br from-[#2D1606]/85 via-[#2D1606]/60 to-transparent" />
        <div className="relative h-full flex flex-col justify-end p-12 text-white">
          <div className="mb-3 text-xs tracking-[0.3em] uppercase text-orange-200">{bizName.split(" ")[0] || "SP Royal"}</div>
          <h1 className="font-display text-5xl font-bold leading-tight max-w-md">
            {bizName}
          </h1>
          <p className="mt-3 text-orange-100/80 max-w-md">
            Operations Manager — Track purchases, usage, sales and live stock all in one place.
          </p>
        </div>
      </div>

      {/* Form side */}
      <div className="flex-1 flex items-center justify-center p-6 bg-[#FFF8F0]">
        <Card className="w-full max-w-md rounded-2xl border-orange-900/10 shadow-xl shadow-orange-900/5">
          <CardContent className="p-8">
            <div className="flex items-center gap-3 mb-6">
              <div className="h-11 w-11 rounded-xl bg-orange-600 text-white font-display font-bold text-lg flex items-center justify-center shadow-lg shadow-orange-600/30">
                SP
              </div>
              <div>
                <div className="font-display font-bold text-slate-900 text-lg leading-tight">{bizName}</div>
                <div className="text-xs text-slate-500">Sign in to continue</div>
              </div>
            </div>

            <form onSubmit={submit} className="space-y-4">
              <div>
                <Label htmlFor="email" className="text-sm font-medium text-slate-700 mb-1.5 block">Email</Label>
                <Input
                  id="email"
                  type="email"
                  data-testid="login-email-input"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@spdhaba.com"
                  className="h-12 rounded-lg"
                />
              </div>
              <div>
                <Label htmlFor="password" className="text-sm font-medium text-slate-700 mb-1.5 block">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPwd ? "text" : "password"}
                    data-testid="login-password-input"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="h-12 rounded-lg pr-12"
                  />
                  <button type="button" onClick={() => setShowPwd((s) => !s)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                    data-testid="toggle-password-visibility">
                    {showPwd ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>
              <Button
                type="submit"
                data-testid="login-submit-button"
                disabled={loading}
                className="w-full h-12 rounded-full bg-orange-600 hover:bg-orange-700 font-medium active:scale-[0.98] transition-all"
              >
                <LogIn size={18} className="mr-2" />
                {loading ? "Signing in..." : "Sign in"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
