package com.sermax.preview;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.inputmethod.InputMethodManager;
import android.content.Context;
import android.widget.*;
import android.text.InputType;
import java.util.Locale;

public class MainActivity extends Activity {
    private final int bg=Color.rgb(7,17,13), panel=Color.rgb(16,31,24), green=Color.rgb(57,232,121), white=Color.rgb(232,242,236), muted=Color.rgb(151,174,160);
    private LinearLayout chat;
    private EditText input;
    private TextView status;
    private ScrollView scroll;
    private boolean mobileMode=true;

    @Override public void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().setStatusBarColor(bg); getWindow().setNavigationBarColor(bg);
        LinearLayout root=new LinearLayout(this); root.setOrientation(1); root.setPadding(dp(14),dp(12),dp(14),dp(12)); root.setBackgroundColor(bg); setContentView(root);
        LinearLayout head=new LinearLayout(this); head.setGravity(Gravity.CENTER_VERTICAL);
        TextView logo=txt("SERMAX",25,green,true); head.addView(logo,new LinearLayout.LayoutParams(0,-2,1)); head.addView(txt("v0.2 OFFLINE",11,muted,true)); root.addView(head);
        root.addView(txt("ASSISTENTE LOCAL • RESPOSTAS BÁSICAS SEM INTERNET",10,muted,false));
        status=txt("● Modo celular • respostas locais",13,white,true); status.setPadding(dp(10),dp(10),dp(10),dp(10)); status.setBackground(round(panel,12));
        LinearLayout.LayoutParams sp=new LinearLayout.LayoutParams(-1,-2); sp.topMargin=dp(10); root.addView(status,sp);
        Button mode=btn("Alternar modo PC / celular"); LinearLayout.LayoutParams mp=new LinearLayout.LayoutParams(-1,dp(44)); mp.topMargin=dp(6); root.addView(mode,mp);
        mode.setOnClickListener(v->{mobileMode=!mobileMode; status.setText(mobileMode?"● Modo celular • respostas locais":"● Modo PC • sem conexão configurada"); bubble("SERMAX",mobileMode?"Modo celular selecionado. Posso responder a comandos básicos sem internet.":"Modo PC selecionado, mas nenhum computador está conectado.",false);});
        root.addView(txt("CONVERSA",11,green,true));
        scroll=new ScrollView(this); chat=new LinearLayout(this); chat.setOrientation(1); chat.setPadding(0,dp(8),0,dp(8)); scroll.addView(chat); root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        bubble("SERMAX","Olá! Sou a versão Android v0.2. O chat já responde a comandos básicos offline. Ainda não sou uma IA completa.",false);
        bubble("SERMAX","Experimente: oi, ajuda, hora, data, quem é você ou status.",false);
        LinearLayout composer=new LinearLayout(this); composer.setGravity(Gravity.CENTER_VERTICAL);
        input=new EditText(this); input.setSingleLine(true); input.setHint("Digite uma mensagem..."); input.setHintTextColor(muted); input.setTextColor(white); input.setTextSize(14); input.setPadding(dp(10),0,dp(10),0); input.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_CAP_SENTENCES); input.setBackground(round(panel,12));
        composer.addView(input,new LinearLayout.LayoutParams(0,dp(50),1)); Button send=btn("Enviar"); LinearLayout.LayoutParams bp=new LinearLayout.LayoutParams(dp(82),dp(50)); bp.leftMargin=dp(7); composer.addView(send,bp); root.addView(composer);
        send.setOnClickListener(v->sendMessage()); input.setOnEditorActionListener((v,a,e)->{sendMessage();return true;});
        TextView foot=txt("OFFLINE • SEM API PAGA • RESPOSTAS LIMITADAS",9,muted,false); foot.setGravity(Gravity.CENTER); foot.setPadding(0,dp(8),0,0); root.addView(foot);
    }
    private void sendMessage(){String m=input.getText().toString().trim(); if(m.isEmpty()){input.setError("Digite uma mensagem");return;} bubble("Você",m,true); input.setText(""); ((InputMethodManager)getSystemService(Context.INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(input.getWindowToken(),0); bubble("SERMAX",answer(m),false);}
    private String answer(String raw){String m=raw.toLowerCase(new Locale("pt","BR"));
        if(m.matches(".*\\b(oi|olá|ola|bom dia|boa tarde|boa noite|e aí|eai)\\b.*")) return "Olá! Estou funcionando e recebi sua mensagem. Como posso ajudar?";
        if(m.contains("ajuda")||m.contains("comandos")) return "Comandos disponíveis offline: 'oi', 'hora', 'data', 'quem é você', 'status' e 'o que você faz'. Para perguntas gerais ainda preciso de um modelo de IA, que não está integrado nesta versão.";
        if(m.contains("hora")) return "A hora deste aparelho é " + android.text.format.DateFormat.format("HH:mm",System.currentTimeMillis()) + ".";
        if(m.contains("data")||m.contains("dia de hoje")) return "Hoje é " + android.text.format.DateFormat.format("dd/MM/yyyy",System.currentTimeMillis()) + ".";
        if(m.contains("quem é você")||m.contains("quem e voce")||m.contains("sermax")) return "Sou o SERMAX Android v0.2, uma prévia com respostas locais básicas. Não sou ainda a IA completa e não estou conectado ao SERMAX Windows.";
        if(m.contains("status")||m.contains("funcionando")) return "Status: aplicativo aberto, mensagem recebida e mecanismo de respostas locais ativo. IA avançada: ainda não integrada.";
        if(m.contains("o que você faz")||m.contains("o que voce faz")) return "No momento respondo a alguns comandos simples sem internet. Para conversar livremente será necessário integrar uma IA local compatível ou um serviço de IA.";
        if(m.contains("obrigado")||m.contains("obrigada")) return "Por nada! Estou aqui. Você pode digitar 'ajuda' para ver os comandos disponíveis.";
        return "Recebi sua mensagem: '" + raw + "'. Ainda não tenho uma IA completa para interpretar perguntas livres. Digite 'ajuda' para ver os comandos offline disponíveis.";
    }
    private void bubble(String who,String msg,boolean user){LinearLayout b=new LinearLayout(this);b.setOrientation(1);b.setPadding(dp(11),dp(9),dp(11),dp(9));b.setBackground(round(user?Color.rgb(17,54,34):panel,12));TextView t=txt(who,11,user?green:muted,true);TextView body=txt(msg,14,white,false);body.setPadding(0,dp(4),0,0);b.addView(t);b.addView(body);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.bottomMargin=dp(7);chat.addView(b,p); if(scroll!=null)scroll.post(()->scroll.fullScroll(ScrollView.FOCUS_DOWN));}
    private TextView txt(String s,int size,int color,boolean bold){TextView t=new TextView(this);t.setText(s);t.setTextSize(size);t.setTextColor(color);if(bold)t.setTypeface(Typeface.DEFAULT,Typeface.BOLD);return t;}
    private Button btn(String s){Button b=new Button(this);b.setText(s);b.setTextSize(12);b.setTextColor(bg);b.setAllCaps(false);b.setTypeface(Typeface.DEFAULT,Typeface.BOLD);b.setBackground(round(green,12));return b;}
    private GradientDrawable round(int c,int r){GradientDrawable d=new GradientDrawable();d.setColor(c);d.setCornerRadius(dp(r));return d;}
    private int dp(int x){return (int)(x*getResources().getDisplayMetrics().density+0.5f);}
}