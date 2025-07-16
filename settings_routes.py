"""
Settings Routes
Routes for managing user settings and configurations
"""

from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import app, db
from models import UserSettings


@app.route('/configuracoes')
@login_required
def configuracoes():
    """Página de configurações do usuário"""
    settings = UserSettings.get_or_create_for_user(current_user.id)
    return render_template('settings/config.html', settings=settings)


@app.route('/configuracoes', methods=['POST'])
@login_required
def configuracoes_salvar():
    """Salvar configurações do usuário"""
    try:
        settings = UserSettings.get_or_create_for_user(current_user.id)
        
        # Atualizar configurações
        settings.openai_api_key = request.form.get('openai_api_key', '').strip()
        settings.consumer_key = request.form.get('consumer_key', '').strip()
        settings.consumer_secret = request.form.get('consumer_secret', '').strip()
        settings.token_key = request.form.get('token_key', '').strip()
        settings.token_secret = request.form.get('token_secret', '').strip()
        settings.fluig_url = request.form.get('fluig_url', '').strip()
        settings.ged_folder_id = request.form.get('ged_folder_id', '').strip()
        
        # Validar URL do Fluig se fornecida
        if settings.fluig_url and not settings.fluig_url.startswith(('http://', 'https://')):
            settings.fluig_url = 'https://' + settings.fluig_url
        
        db.session.commit()
        
        flash('Configurações salvas com sucesso!', 'success')
        return redirect(url_for('configuracoes'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao salvar configurações: {str(e)}', 'error')
        return redirect(url_for('configuracoes'))


@app.route('/configuracoes/testar-openai')
@login_required
def testar_openai():
    """Testar conexão com OpenAI"""
    settings = UserSettings.get_or_create_for_user(current_user.id)
    
    if not settings.has_openai_key:
        return jsonify({'success': False, 'message': 'OpenAI API Key não configurada'})
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=settings.openai_api_key)
        
        # Teste simples
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5
        )
        
        return jsonify({
            'success': True, 
            'message': 'Conexão com OpenAI bem-sucedida!',
            'model': response.model,
            'usage': response.usage.total_tokens if response.usage else 0
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro na conexão: {str(e)}'})


@app.route('/configuracoes/testar-fluig')
@login_required
def testar_fluig():
    """Testar conexão com Fluig"""
    settings = UserSettings.get_or_create_for_user(current_user.id)
    
    if not settings.has_fluig_config:
        return jsonify({'success': False, 'message': 'Configuração Fluig incompleta'})
    
    try:
        import requests
        
        # Testar URL do Fluig
        response = requests.get(settings.fluig_url, timeout=10)
        
        if response.status_code == 200:
            return jsonify({
                'success': True,
                'message': 'Conexão com Fluig bem-sucedida!',
                'status_code': response.status_code
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Erro HTTP {response.status_code}'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro na conexão: {str(e)}'})


@app.route('/configuracoes/limpar/<string:config_type>')
@login_required
def limpar_configuracao(config_type):
    """Limpar configuração específica"""
    try:
        settings = UserSettings.get_or_create_for_user(current_user.id)
        
        if config_type == 'openai':
            settings.openai_api_key = None
            message = 'Configuração OpenAI limpa com sucesso!'
        elif config_type == 'twitter':
            settings.consumer_key = None
            settings.consumer_secret = None
            settings.token_key = None
            settings.token_secret = None
            message = 'Configuração Twitter/X limpa com sucesso!'
        elif config_type == 'fluig':
            settings.fluig_url = None
            settings.ged_folder_id = None
            message = 'Configuração Fluig limpa com sucesso!'
        else:
            flash('Tipo de configuração inválido!', 'error')
            return redirect(url_for('configuracoes'))
        
        db.session.commit()
        flash(message, 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao limpar configuração: {str(e)}', 'error')
    
    return redirect(url_for('configuracoes'))


@app.route('/api/configuracoes/status')
@login_required
def api_configuracoes_status():
    """API para verificar status das configurações"""
    settings = UserSettings.get_or_create_for_user(current_user.id)
    
    return jsonify({
        'openai': {
            'configured': settings.has_openai_key,
            'status': 'Configurada' if settings.has_openai_key else 'Não configurada'
        },
        'twitter': {
            'configured': settings.has_twitter_config,
            'status': 'Configurada' if settings.has_twitter_config else 'Não configurada'
        },
        'fluig': {
            'configured': settings.has_fluig_config,
            'status': 'Configurada' if settings.has_fluig_config else 'Não configurada'
        }
    })