<Qucs Schematic 26.1.1>
<Properties>
  <View=0,0,1199,684,1,0,0>
  <Grid=10,10,1>
  <DataSet=esquematico.dat>
  <DataDisplay=esquematico.dpl>
  <OpenDisplay=0>
  <Script=esquematico.m>
  <RunScript=0>
  <showFrame=0>
  <FrameText0=Title>
  <FrameText1=Drawn By:>
  <FrameText2=Date:>
  <FrameText3=Revision:>
</Properties>
<Symbol>
  <.PortSym 40 20 1 0 VCC>
  <.PortSym 40 60 2 0 GND>
  <.PortSym 40 100 3 0 PortaAnalogica>
</Symbol>
<Components>
  <Port VCC 1 220 180 -23 12 0 0 "1" 0 "analog" 0>
  <Port GND 1 220 340 -23 12 0 0 "2" 0 "analog" 0>
  <Port PortaAnalogica 1 220 270 -23 12 0 0 "3" 0 "analog" 0>
  <R R1 1 430 300 15 -26 0 1 "1 kOhm" 1 "26.85" 0 "0.0" 0 "0.0" 0 "26.85" 0 "US" 0>
  <R LDR 1 430 210 15 -26 0 1 "1 kOhm" 0 "26.85" 0 "0.0" 0 "0.0" 0 "26.85" 0 "european" 0>
</Components>
<Wires>
  <220 340 430 340 "" 0 0 0 "">
  <430 340 430 330 "" 0 0 0 "">
  <220 270 430 270 "" 0 0 0 "">
  <430 270 430 240 "" 0 0 0 "">
  <220 180 430 180 "" 0 0 0 "">
</Wires>
<Diagrams>
</Diagrams>
<Paintings>
  <Rectangle 100 100 180 300 #000000 1 1 #c0c0c0 1 0>
  <Text 150 130 12 #000000 0 "Heltec ESP">
  <Arrow 510 140 -40 40 20 8 #000000 1 1 0>
  <Arrow 510 190 -40 40 20 8 #000000 1 1 0>
</Paintings>
