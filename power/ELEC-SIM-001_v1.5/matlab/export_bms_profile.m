%% EXPORT_BMS_PROFILE  Write a load profile for ELEC-SIM-001 v1.5.
%
% Workstream: Kiboard Warriors (ELEC-013 to ELEC-015).
% Companion to: one_sided_battery_current.m (EXO > Electrical > Test Data).
%
% Put this file in the same folder as one_sided_battery_current.m and the two
% Comparison_Data XML files, then run it. It writes a CSV that the Python
% simulation reads, so a BMS result can be traced to the Electrical control
% model rather than to the Python port of it.
%
% The CSV column contract (the Python side checks for these names):
%   t_s         time from the start of the exported window, seconds
%   P_W         DC-bus power, positive discharges the pack
%   I_A         battery current at the fixed bus voltage, as the MATLAB model
%               reports it. The Python side re-solves current against the live
%               pack voltage and uses this column only for comparison.
%   phase_pct   gait cycle percentage
%
% Prefer P_W. A profile with only I_A cannot respond to pack voltage sag or to
% a controller derate, so it cannot be used for the closed-loop scenarios.
%
% Usage:
%   export_bms_profile                       % defaults below
%   export_bms_profile('assist',0.5,'cycles',6)

function export_bms_profile(varargin)

opt = struct( ...
    'file',        "PostStroke_Moco_Comparison_Data_Hemi.xml", ...
    'out',         "gait_profile_for_bms.csv", ...
    'assist',      1.0, ...     % fraction of the weak-to-strong torque gap
    'weakSide',    "auto", ...
    'velocityFrom', "weak", ...
    'tauMax',      20, ...      % Nm at the joint, AK80-9 peak is 22
    'hotFactor',   1.3, ...     % winding-loss multiplier
    'V',           48, ...      % fixed bus voltage used for the I_A column
    'auxWatts',    45, ...      % Jetson 40 W + Teensy and sensors 5 W
    'includeAux',  true, ...
    'regenCredit', false, ...   % true credits braking power back to the bus
    'cycles',      4);
for k = 1:2:numel(varargin)
    opt.(varargin{k}) = varargin{k+1};
end

%% ---- read the comparison data (same reader as one_sided_battery_current.m)
s = readstruct(opt.file);
S = s.Signals.Sample;
t = double(string([S.time_sAttribute]))';
M = [S.JointMoments_Nm];
W = [S.AngularVelocities_rad_s];

tauL = [[M.LeftHip]', [M.LeftKnee]'];
tauR = [[M.RightHip]', [M.RightKnee]'];
wL   = [[W.LeftHip]', [W.LeftKnee]'];
wR   = [[W.RightHip]', [W.RightKnee]'];

if max(abs([tauL(end,:), tauR(end,:)] - [tauL(1,:), tauR(1,:)])) < 1e-6
    t(end) = []; tauL(end,:) = []; tauR(end,:) = []; wL(end,:) = []; wR(end,:) = [];
end
n = numel(t);
pct = 100*(0:n-1)'/n;

%% ---- weak and strong side
weakSide = opt.weakSide;
if weakSide == "auto"
    if sqrt(mean(tauL(:).^2)) < sqrt(mean(tauR(:).^2))
        weakSide = "Left";
    else
        weakSide = "Right";
    end
end
if weakSide == "Left"
    tauW = tauL; wW = wL; tauS = tauR; wS = wR;
else
    tauW = tauR; wW = wR; tauS = tauL; wS = wL;
end

%% ---- align the two strides (same correlation search as the source model)
score = zeros(n,1);
for k = 0:n-1
    wShift = circshift(wS, k);
    c1 = corrcoef(wShift(:,1), wW(:,1));
    c2 = corrcoef(wShift(:,2), wW(:,2));
    score(k+1) = c1(1,2) + c2(1,2);
end
[~, best] = max(score);
shift = best - 1;
tauTarget = circshift(tauS, shift);
wTarget   = circshift(wS, shift);
if opt.velocityFrom == "strong"
    w = wTarget;
else
    w = wW;
end

%% ---- drivetrain, identical to exoModel() in one_sided_battery_current.m
N = 9; eg = 0.90; ec = 0.95; Km = 0.2387;

gap   = tauTarget - tauW;
taReq = opt.assist * gap;
ta    = min(max(taReq, -opt.tauMax), opt.tauMax);

Pmech = ta .* w;
drive = Pmech >= 0;
tm = abs(ta)/(N*eg);  tm(~drive) = abs(ta(~drive))*eg/N;
Pm = Pmech/eg;        Pm(~drive) = Pmech(~drive)*eg;
Pe = Pm + opt.hotFactor*(tm/Km).^2;

if opt.regenCredit
    Pb = Pe/ec;
    Pb(Pe < 0) = Pe(Pe < 0)*ec*0.80;   % 0.80: regen_conversion_eff, ASSUMED
else
    Pb = Pe/ec;
    Pb(Pe <= 0) = 0;                   % source-model behaviour, no regen credit
end

Pbus = sum(Pb, 2);
if opt.includeAux
    Pbus = Pbus + opt.auxWatts;
end

%% ---- repeat the cycle and write the CSV
cycle_s = (t(end) - t(1)) * n / max(n-1, 1);
T = []; PW = []; PH = [];
for c = 0:opt.cycles-1
    T  = [T;  (t - t(1)) + c*cycle_s]; %#ok<AGROW>
    PW = [PW; Pbus];                   %#ok<AGROW>
    PH = [PH; pct];                    %#ok<AGROW>
end
IA = PW / opt.V;

out = table(T, PW, IA, PH, 'VariableNames', {'t_s','P_W','I_A','phase_pct'});
writetable(out, opt.out);

fprintf('Wrote %s: %d rows, %.3f s, %d cycles\n', opt.out, height(out), T(end), opt.cycles);
fprintf('  weak side %s, strong leg shifted %.1f%% of the cycle\n', weakSide, 100*shift/n);
fprintf('  bus power: peak %.1f W, mean %.1f W, min %.1f W\n', max(PW), mean(PW), min(PW));
fprintf('  battery current at the fixed %.0f V: peak %.2f A, mean %.2f A\n', ...
        opt.V, max(IA), mean(IA));
fprintf('  aux load %s, regen credit %s\n', ...
        string(opt.includeAux), string(opt.regenCredit));
end
